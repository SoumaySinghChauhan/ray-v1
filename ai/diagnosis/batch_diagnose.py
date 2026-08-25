#!/usr/bin/env python3
"""
Batch offline LLM diagnosis.

Processes all 1,000 opportunities ONCE and caches results.
The benchmark must use cached results only.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import time
from datetime import datetime, timezone
from typing import Any
import pandas as pd
from pydantic import ValidationError

from config import get_config
from simulator.generation.data_loaders import (
    load_observable_dataset,
    load_historical_transactions,
)
from ai.diagnosis.schema import (
    LLMDiagnosticOutput,
    DiagnosisRecord,
    DiagnosisManifest,
    DiagnosticStatus,
)
from ai.diagnosis.prompt import (
    DIAGNOSIS_SYSTEM_PROMPT,
    DIAGNOSIS_PROMPT_VERSION,
    create_diagnosis_prompt,
    format_diagnosis_for_cache,
)


class LLMDiagnosisError(Exception):
    """Raised when LLM diagnosis fails."""
    pass


class BatchDiagnoser:
    """Batch offline diagnosis processor."""

    def __init__(
        self,
        dataset_path: Path,
        output_path: Path,
        llm_provider: str = "anthropic",
        model: str | None = None,
        max_retries: int = 3,
        dry_run: bool = False,
    ):
        """
        Initialize batch diagnoser.

        Args:
            dataset_path: Path to frozen dataset
            output_path: Path for diagnosis output
            llm_provider: LLM provider (anthropic, openai, or gemini)
            model: Model name override
            max_retries: Maximum retry attempts per opportunity
            dry_run: If True, skip actual LLM calls (for testing)
        """
        self.dataset_path = dataset_path
        self.output_path = output_path
        self.llm_provider = llm_provider
        self.max_retries = max_retries
        self.dry_run = dry_run

        self.config = get_config()

        # Model selection
        if model:
            self.model = model
        elif llm_provider == "anthropic":
            self.model = "claude-3-5-sonnet-20241022"
        elif llm_provider == "openai":
            self.model = "gpt-4-turbo-preview"
        elif llm_provider == "gemini":
            self.model = "gemini-1.5-pro"
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")

        # Initialize LLM client
        if not dry_run:
            self._init_llm_client()

        # Statistics
        self.stats = {
            "total": 0,
            "successful": 0,
            "low_confidence": 0,
            "schema_failed": 0,
            "llm_failed": 0,
            "total_retries": 0,
            "total_duration_ms": 0.0,
        }

        # Create output directory
        self.output_path.mkdir(parents=True, exist_ok=True)

    def _init_llm_client(self):
        """Initialize LLM API client."""
        if self.llm_provider == "anthropic":
            import anthropic
            import os
            api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.client = anthropic.Anthropic(api_key=api_key)

        elif self.llm_provider == "openai":
            import openai
            import os
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self.client = openai.OpenAI(api_key=api_key)

        elif self.llm_provider == "gemini":
            import google.generativeai as genai
            import os
            api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model)

    def diagnose(self):
        """Run batch diagnosis on all opportunities."""

        print("=" * 70)
        print("RAY V1 BATCH OFFLINE DIAGNOSIS")
        print("=" * 70)
        print(f"Provider: {self.llm_provider}")
        print(f"Model: {self.model}")
        print(f"Max retries: {self.max_retries}")
        print(f"Dry run: {self.dry_run}")
        print(f"Output: {self.output_path}")
        print()

        # Load data
        print("Loading opportunities...")
        df_opportunities = load_observable_dataset(self.dataset_path)
        print(f"  ✓ Loaded {len(df_opportunities)} opportunities")
        print()

        # Process each opportunity
        diagnoses = []
        start_time = time.time()

        for idx, row in df_opportunities.iterrows():
            if (idx + 1) % 100 == 0:
                print(f"  ... processed {idx + 1}/{len(df_opportunities)}")

            diagnosis = self._diagnose_opportunity(row)
            diagnoses.append(diagnosis)

        total_duration = time.time() - start_time

        print(f"  ✓ Completed {len(diagnoses)} diagnoses")
        print()

        # Save results
        print("Saving results...")
        self._save_results(diagnoses, total_duration)
        print()

        # Print statistics
        self._print_statistics()

        print("=" * 70)
        print("DIAGNOSIS COMPLETE")
        print("=" * 70)

    def _diagnose_opportunity(self, row: pd.Series) -> dict[str, Any]:
        """
        Diagnose a single opportunity with retry logic.

        Args:
            row: Opportunity row from dataset

        Returns:
            Diagnosis record
        """
        opportunity_id = row["opportunity_id"]
        customer_id = row["customer_id"]

        # Prepare customer history summary
        history_summary = {
            "historical_payment_count": int(row["historical_payment_count"]),
            "historical_success_count": int(row["historical_success_count"]),
            "historical_failure_count": int(row["historical_failure_count"]),
            "historical_recovery_count": int(row["historical_recovery_count"]),
            "historical_recovery_rate": float(row["historical_recovery_rate"]),
            "customer_lifetime_value": float(row["customer_lifetime_value"]),
            "avg_payment_amount": float(row["avg_payment_amount"]),
            "days_since_first_payment": int(row["days_since_first_payment"]),
        }

        # Create prompt
        prompt = create_diagnosis_prompt(
            payment_amount=float(row["amount"]),
            payment_method=row["payment_method"],
            currency=row["currency"],
            failure_class=row["failure_class"],
            failure_description=row["failure_description"],
            customer_history_summary=history_summary,
        )

        # Attempt diagnosis with retries
        for attempt in range(self.max_retries):
            try:
                llm_output, duration_ms = self._call_llm(prompt)

                # Validate schema
                validated = LLMDiagnosticOutput(**llm_output)

                # Determine status
                if validated.confidence < self.config.recovery.llm_diagnosis_confidence_threshold:
                    status = DiagnosticStatus.LOW_CONFIDENCE
                    self.stats["low_confidence"] += 1
                else:
                    status = DiagnosticStatus.SUCCESS

                self.stats["successful"] += 1
                self.stats["total_retries"] += attempt
                self.stats["total_duration_ms"] += duration_ms

                return format_diagnosis_for_cache(
                    opportunity_id=opportunity_id,
                    customer_id=customer_id,
                    llm_output=validated.model_dump(),
                    config=self.config,
                    model_version=self.model,
                    retry_count=attempt,
                    duration_ms=duration_ms,
                    status=status.value,
                )

            except ValidationError as e:
                self.stats["schema_failed"] += 1
                if attempt == self.max_retries - 1:
                    # Final attempt failed
                    return self._create_safe_halt_record(
                        opportunity_id,
                        customer_id,
                        DiagnosticStatus.SCHEMA_VALIDATION_FAILED,
                        attempt,
                    )

            except Exception as e:
                self.stats["llm_failed"] += 1
                if attempt == self.max_retries - 1:
                    # Final attempt failed
                    return self._create_safe_halt_record(
                        opportunity_id,
                        customer_id,
                        DiagnosticStatus.LLM_CALL_FAILED,
                        attempt,
                    )

            # Brief backoff before retry
            time.sleep(0.5 * (attempt + 1))

        # Should not reach here
        return self._create_safe_halt_record(
            opportunity_id,
            customer_id,
            DiagnosticStatus.SAFE_HALT,
            self.max_retries,
        )

    def _call_llm(self, prompt: str) -> tuple[dict[str, Any], float]:
        """
        Call LLM API.

        Args:
            prompt: User prompt

        Returns:
            (parsed_response, duration_ms)
        """
        if self.dry_run:
            # Return mock response for testing
            return {
                "diagnostic_class": "SOFT_DECLINE",
                "reason_codes": ["TEMPORARY_FAILURE", "STRONG_PAYMENT_HISTORY"],
                "diagnostic_summary": "Dry run mock diagnosis.",
                "confidence": 0.85,
            }, 100.0

        start_time = time.time()

        if self.llm_provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=DIAGNOSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

        elif self.llm_provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content

        elif self.llm_provider == "gemini":
            full_prompt = f"{DIAGNOSIS_SYSTEM_PROMPT}\n\n{prompt}"
            response = self.client.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 1024,
                }
            )

            content = response.text

        duration_ms = (time.time() - start_time) * 1000

        # Parse JSON
        parsed = json.loads(content)

        return parsed, duration_ms

    def _create_safe_halt_record(
        self,
        opportunity_id: str,
        customer_id: str,
        status: DiagnosticStatus,
        retry_count: int,
    ) -> dict[str, Any]:
        """Create safe halt diagnosis record."""
        return {
            "opportunity_id": opportunity_id,
            "customer_id": customer_id,
            "diagnostic_class": "UNKNOWN",
            "reason_codes": ["INSUFFICIENT_INFORMATION"],
            "diagnostic_summary": f"Diagnosis failed: {status.value}",
            "confidence": 0.0,
            "diagnostic_status": status.value,
            "diagnosis_version": "1.0.0",
            "diagnosis_prompt_version": DIAGNOSIS_PROMPT_VERSION,
            "diagnosis_model_version": self.model,
            "diagnosis_schema_version": "1.0.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "retry_count": retry_count,
            "llm_call_duration_ms": None,
        }

    def _save_results(self, diagnoses: list[dict[str, Any]], total_duration: float):
        """Save diagnosis results."""

        # Save as parquet
        df_diagnoses = pd.DataFrame(diagnoses)
        diagnoses_path = self.output_path / "diagnoses.parquet"
        df_diagnoses.to_parquet(diagnoses_path, index=False)
        print(f"  ✓ Saved {len(df_diagnoses)} diagnoses to {diagnoses_path}")

        # Save manifest
        manifest = DiagnosisManifest(
            diagnosis_version="1.0.0",
            diagnosis_prompt_version=DIAGNOSIS_PROMPT_VERSION,
            diagnosis_model_version=self.model,
            diagnosis_schema_version="1.0.0",
            llm_provider=self.llm_provider,
            generation_timestamp=datetime.now(timezone.utc).isoformat(),
            opportunities_total=len(diagnoses),
            diagnoses_successful=self.stats["successful"],
            diagnoses_low_confidence=self.stats["low_confidence"],
            diagnoses_failed=self.stats["schema_failed"] + self.stats["llm_failed"],
            total_llm_calls=len(diagnoses),
            total_retries=self.stats["total_retries"],
            total_duration_seconds=total_duration,
            confidence_threshold=self.config.recovery.llm_diagnosis_confidence_threshold,
        )

        manifest_path = self.output_path / "diagnosis_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest.model_dump(), f, indent=2)
        print(f"  ✓ Saved manifest to {manifest_path}")

    def _print_statistics(self):
        """Print diagnosis statistics."""
        print("DIAGNOSIS STATISTICS")
        print("=" * 70)
        print(f"Total opportunities: {self.stats['successful'] + self.stats['schema_failed'] + self.stats['llm_failed']}")
        print(f"Successful: {self.stats['successful']}")
        print(f"  - High confidence: {self.stats['successful'] - self.stats['low_confidence']}")
        print(f"  - Low confidence: {self.stats['low_confidence']}")
        print(f"Schema validation failed: {self.stats['schema_failed']}")
        print(f"LLM call failed: {self.stats['llm_failed']}")
        print(f"Total retries: {self.stats['total_retries']}")
        if self.stats['successful'] > 0:
            avg_duration = self.stats['total_duration_ms'] / self.stats['successful']
            print(f"Average call duration: {avg_duration:.0f}ms")
        print()


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Batch offline LLM diagnosis")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/v1.0.0"),
        help="Dataset path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/v1.0.0/diagnoses"),
        help="Output path",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "gemini"],
        default="anthropic",
        help="LLM provider",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model override",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries per opportunity",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run (no actual LLM calls)",
    )

    args = parser.parse_args()

    diagnoser = BatchDiagnoser(
        dataset_path=args.dataset,
        output_path=args.output,
        llm_provider=args.provider,
        model=args.model,
        max_retries=args.max_retries,
        dry_run=args.dry_run,
    )

    diagnoser.diagnose()


if __name__ == "__main__":
    main()
