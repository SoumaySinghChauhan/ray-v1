#!/usr/bin/env python3
"""
STAGE A/B/C Pilot Diagnosis Script for RAY V1.

Processes a limited number of opportunities (10, 100, or full 1000)
with real Gemini API to verify quality before full batch.

EXPERIMENTAL RULES:
- Uses ONLY observable fields
- NO hidden ground truth sent to LLM
- Real Gemini API calls (gemini-3.6-flash)
- Caches results for reproducibility
- STOPS after pilot and reports quality
"""

import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import time
from datetime import datetime, timezone
import pandas as pd
from pydantic import ValidationError

from ai.diagnosis.schema import (
    LLMDiagnosticOutput,
    DiagnosticStatus,
)
from ai.diagnosis.prompt import (
    DIAGNOSIS_SYSTEM_PROMPT,
    DIAGNOSIS_PROMPT_VERSION,
    create_diagnosis_prompt,
    format_diagnosis_for_cache,
)
from ai.diagnosis.error_capture import capture_api_error, verify_no_secrets
from ai.diagnosis.confidence_analysis import (
    analyze_confidence_distribution,
    format_confidence_report,
)


class PilotDiagnoser:
    """Pilot diagnosis processor with quality gates."""

    def __init__(
        self,
        dataset_path: Path,
        output_path: Path,
        limit: int,
        provider: str = "gemini",
        model: str = None,
        max_retries: int = 3,
    ):
        self.dataset_path = dataset_path
        self.output_path = output_path
        self.limit = limit
        self.provider = provider
        self.max_retries = max_retries

        # Initialize provider-specific client
        import os

        if provider == "local":
            # Local Ollama provider
            from ai.diagnosis.local_provider import LocalDiagnosisProvider

            if model is None:
                model = "qwen3:4b-instruct"

            ollama_host = os.getenv("LOCAL_OLLAMA_HOST", "http://localhost:11434")

            self.client = LocalDiagnosisProvider(
                model=model,
                host=ollama_host,
                temperature=0.7,
                num_ctx=2048,
            )
            self.model_name = model
            self.api_key = None  # No API key for local

        elif provider == "gemini":
            # Gemini provider
            from google import genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")

            if model is None:
                model = "gemini-3.6-flash"

            self.client = genai.Client(api_key=api_key)
            self.model_name = model
            self.api_key = api_key  # Store for error sanitization only

        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Stats
        self.stats = {
            "total": 0,
            "successful": 0,
            "schema_failed": 0,
            "llm_failed": 0,
            "total_retries": 0,
            "total_duration_ms": 0.0,
            "latencies_ms": [],
        }

        # Error tracking
        self.error_log = []

        self.output_path.mkdir(parents=True, exist_ok=True)

    def diagnose(self):
        """Run pilot diagnosis."""

        print("=" * 70)
        print(f"RAY V1 PILOT DIAGNOSIS — {self.limit} OPPORTUNITIES")
        print("=" * 70)
        print(f"Provider: {self.provider}")
        print(f"Model: {self.model_name}")
        print(f"Max retries: {self.max_retries}")
        print(f"Output: {self.output_path}")
        if self.provider == "local":
            model_info = self.client.get_model_info()
            print(f"Model size: {model_info.get('size_gb', 0):.2f} GB")
            print(f"Parameters: {model_info.get('parameter_size', 'unknown')}")
        print()

        # Load opportunities
        print("Loading opportunities...")
        opps = pd.read_parquet(
            self.dataset_path / "observable" / "current_opportunities.parquet"
        )
        print(f"  ✓ Loaded {len(opps)} total opportunities")
        print()

        # Take first N
        opps_pilot = opps.head(self.limit)
        print(f"Processing first {len(opps_pilot)} opportunities...")
        print()

        # Process each
        diagnoses = []
        start_time = time.time()

        for idx, row in opps_pilot.iterrows():
            self.stats["total"] += 1

            if (self.stats["total"]) % 10 == 0:
                print(f"  ... processed {self.stats['total']}/{len(opps_pilot)}")

            diagnosis = self._diagnose_opportunity(row)
            diagnoses.append(diagnosis)

        total_duration = time.time() - start_time

        print(f"  ✓ Completed {len(diagnoses)} diagnoses")
        print()

        # Save
        print("Saving results...")
        self._save_results(diagnoses, total_duration)
        print()

        # Quality check
        self._quality_check(diagnoses)

        # Print confidence report
        print()
        df_for_confidence = pd.DataFrame(diagnoses)
        print(format_confidence_report(analyze_confidence_distribution(df_for_confidence)))

        print("=" * 70)
        print(f"PILOT DIAGNOSIS COMPLETE — {self.limit} OPPORTUNITIES")
        print("=" * 70)

    def _diagnose_opportunity(self, row: pd.Series) -> dict:
        """Diagnose single opportunity with retry."""

        opportunity_id = row["opportunity_id"]
        customer_id = row["customer_id"]

        # Customer history summary (OBSERVABLE ONLY)
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

        # Retry logic
        for attempt in range(self.max_retries):
            start_time = time.time()  # Track timing for error capture
            try:
                llm_output, duration_ms = self._call_llm(prompt)

                # Validate schema
                validated = LLMDiagnosticOutput(**llm_output)

                # Success
                self.stats["successful"] += 1
                self.stats["total_retries"] += attempt
                self.stats["total_duration_ms"] += duration_ms
                self.stats["latencies_ms"].append(duration_ms)

                return {
                    "opportunity_id": opportunity_id,
                    "customer_id": customer_id,
                    "diagnostic_class": validated.diagnostic_class,
                    "reason_codes": [str(r) for r in validated.reason_codes],
                    "diagnostic_summary": validated.diagnostic_summary,
                    "confidence": validated.confidence,
                    "diagnostic_status": "success",
                    "diagnosis_version": "1.0.1-pilot",
                    "diagnosis_prompt_version": DIAGNOSIS_PROMPT_VERSION,
                    "diagnosis_model_version": self.model_name,
                    "diagnosis_schema_version": "1.0.0",
                    "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                    "retry_count": attempt,
                    "llm_call_duration_ms": duration_ms,
                }

            except ValidationError as e:
                self.stats["schema_failed"] += 1

                # Capture error metadata
                error_record = capture_api_error(
                    exception=e,
                    opportunity_id=opportunity_id,
                    retry_number=attempt,
                    api_key=self.api_key,
                    latency_ms=duration_ms if 'duration_ms' in locals() else None,
                )
                self.error_log.append(error_record)

                if attempt == self.max_retries - 1:
                    return self._create_failed_record(
                        opportunity_id, customer_id, "schema_failed", attempt
                    )

            except Exception as e:
                self.stats["llm_failed"] += 1

                # Capture error metadata (measure latency even for failures)
                latency_ms = None
                if 'start_time' in locals():
                    latency_ms = (time.time() - start_time) * 1000

                error_record = capture_api_error(
                    exception=e,
                    opportunity_id=opportunity_id,
                    retry_number=attempt,
                    api_key=self.api_key,
                    latency_ms=latency_ms,
                )
                self.error_log.append(error_record)

                if attempt == self.max_retries - 1:
                    return self._create_failed_record(
                        opportunity_id, customer_id, "llm_failed", attempt
                    )

            time.sleep(0.5 * (attempt + 1))

        return self._create_failed_record(
            opportunity_id, customer_id, "max_retries", self.max_retries
        )

    def _call_llm(self, prompt: str) -> tuple[dict, float]:
        """Call LLM (provider-agnostic)."""

        if self.provider == "local":
            # Local Ollama provider
            return self.client.generate(
                system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
                user_prompt=prompt,
            )

        elif self.provider == "gemini":
            # Gemini provider
            start_time = time.time()

            full_prompt = f"{DIAGNOSIS_SYSTEM_PROMPT}\n\n{prompt}\n\nReturn ONLY valid JSON."

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config={
                    "temperature": 0.7,
                    "max_output_tokens": 1024,
                    "response_mime_type": "application/json",
                },
            )

            duration_ms = (time.time() - start_time) * 1000

            # Parse JSON
            parsed = json.loads(response.text)

            return parsed, duration_ms

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _create_failed_record(
        self, opp_id: str, cust_id: str, status: str, retries: int
    ) -> dict:
        """Create failed diagnosis record."""
        return {
            "opportunity_id": opp_id,
            "customer_id": cust_id,
            "diagnostic_class": "UNKNOWN",
            "reason_codes": ["DIAGNOSIS_FAILED"],
            "diagnostic_summary": f"Diagnosis failed: {status}",
            "confidence": 0.0,
            "diagnostic_status": status,
            "diagnosis_version": "1.0.1-pilot",
            "diagnosis_prompt_version": DIAGNOSIS_PROMPT_VERSION,
            "diagnosis_model_version": self.model_name,
            "diagnosis_schema_version": "1.0.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "retry_count": retries,
            "llm_call_duration_ms": None,
        }

    def _save_results(self, diagnoses: list[dict], total_duration: float):
        """Save diagnosis results."""

        # Save parquet
        df = pd.DataFrame(diagnoses)
        df_path = self.output_path / f"diagnoses_pilot_{self.limit}.parquet"
        df.to_parquet(df_path, index=False)
        print(f"  ✓ Saved {len(df)} diagnoses to {df_path.name}")

        # Save error log
        if self.error_log:
            error_log_path = self.output_path / f"error_log_pilot_{self.limit}.json"

            # Verify no secrets in error log before saving
            error_log_str = json.dumps(self.error_log)
            if not verify_no_secrets(error_log_str, [self.api_key]):
                print("  ⚠️  WARNING: API key found in error log - sanitizing")
                # Re-sanitize entire log
                for record in self.error_log:
                    if self.api_key and self.api_key in record.get("error_message", ""):
                        record["error_message"] = record["error_message"].replace(
                            self.api_key, "[REDACTED_API_KEY]"
                        )

            with open(error_log_path, "w") as f:
                json.dump(self.error_log, f, indent=2)
            print(f"  ✓ Saved {len(self.error_log)} error records to {error_log_path.name}")

        # Analyze confidence distribution
        confidence_analysis = analyze_confidence_distribution(df)
        confidence_report = format_confidence_report(confidence_analysis)

        confidence_report_path = self.output_path / f"confidence_report_pilot_{self.limit}.txt"
        with open(confidence_report_path, "w") as f:
            f.write(confidence_report)
        print(f"  ✓ Saved confidence analysis to {confidence_report_path.name}")

        # Save manifest with error summary
        manifest = {
            "pilot_size": self.limit,
            "diagnosis_version": "1.1.0-pilot" if self.provider == "local" else "1.0.1-pilot",
            "diagnosis_prompt_version": DIAGNOSIS_PROMPT_VERSION,
            "diagnosis_model_version": self.model_name,
            "diagnosis_schema_version": "1.0.0",
            "llm_provider": self.provider,
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "opportunities_total": len(diagnoses),
            "diagnoses_successful": self.stats["successful"],
            "diagnoses_failed": self.stats["schema_failed"] + self.stats["llm_failed"],
            "total_llm_calls": len(diagnoses),
            "total_retries": self.stats["total_retries"],
            "total_duration_seconds": total_duration,
            "error_summary": {
                "total_errors": len(self.error_log),
                "transient_errors": len([e for e in self.error_log if e.get("failure_category") == "transient"]),
                "permanent_errors": len([e for e in self.error_log if e.get("failure_category") == "permanent"]),
                "error_reasons": self._summarize_error_reasons(),
            },
            "confidence_summary": {
                "unique_values": confidence_analysis.get("unique_values", {}).get("count", 0),
                "mean": confidence_analysis.get("confidence_statistics", {}).get("mean"),
                "range": [
                    confidence_analysis.get("confidence_statistics", {}).get("min"),
                    confidence_analysis.get("confidence_statistics", {}).get("max"),
                ],
            },
        }

        manifest_path = self.output_path / f"manifest_pilot_{self.limit}.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"  ✓ Saved manifest to {manifest_path.name}")

    def _summarize_error_reasons(self) -> dict[str, int]:
        """Summarize error reasons from error log."""
        reasons = {}
        for error in self.error_log:
            reason = error.get("error_reason", "UNKNOWN")
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons

    def _quality_check(self, diagnoses: list[dict]):
        """Run quality gate checks."""

        print("QUALITY CHECK")
        print("=" * 70)

        df = pd.DataFrame(diagnoses)

        # 1. Successes
        successful = df[df["diagnostic_status"] == "success"]
        print(f"Successful diagnoses: {len(successful)}/{len(df)}")

        if len(successful) == 0:
            print("❌ FAILED: No successful diagnoses")
            return

        # 2. Unique summaries
        unique_summaries = df["diagnostic_summary"].nunique()
        print(f"Unique summaries: {unique_summaries}")

        # Check for mock text
        mock_text = "Dry run mock diagnosis"
        has_mock = df["diagnostic_summary"].str.contains(mock_text, case=False).any()
        if has_mock:
            print(f"❌ FAILED: Found mock text '{mock_text}'")
            return
        print("✓ No mock text found")

        # Check for uniformity
        if unique_summaries == 1 and len(df) > 1:
            print("❌ FAILED: All summaries identical (suspicious)")
            return
        print("✓ Summaries show variation")

        # 3. Diagnostic classes
        classes = df["diagnostic_class"].value_counts()
        print(f"Diagnostic classes: {len(classes)} unique")
        for cls, count in classes.items():
            print(f"  {cls}: {count}")

        # 4. Confidence distribution
        print(f"Confidence: min={df['confidence'].min():.2f}, max={df['confidence'].max():.2f}, mean={df['confidence'].mean():.2f}")
        unique_confidence = df["confidence"].nunique()
        print(f"Unique confidence values: {unique_confidence}")

        if unique_confidence == 1 and len(df) > 1:
            print("⚠️  WARNING: All confidence values identical")
        else:
            print("✓ Confidence shows variation")

        # 5. Latency
        if self.stats["latencies_ms"]:
            latencies = self.stats["latencies_ms"]
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            print(f"Latency: min={min_latency:.0f}ms, max={max_latency:.0f}ms, avg={avg_latency:.0f}ms")

            if avg_latency < 100:
                print("⚠️  WARNING: Very fast latency (< 100ms) - may not be real API")
            else:
                print("✓ Latency consistent with real API calls")

        # 6. Retries
        print(f"Total retries: {self.stats['total_retries']}")

        # 7. Schema failures
        print(f"Schema failures: {self.stats['schema_failed']}")
        print(f"LLM failures: {self.stats['llm_failed']}")

        print()

        # Overall gate
        if len(successful) >= self.limit * 0.8:  # 80% success rate
            print("=" * 70)
            print(f"✅ PILOT QUALITY CHECK PASSED ({self.limit} opportunities)")
            print("=" * 70)
        else:
            print("=" * 70)
            print(f"⚠️  PILOT QUALITY CHECK: LOW SUCCESS RATE")
            print("=" * 70)


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Pilot diagnosis for RAY V1")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/v1.0.0"),
        help="Dataset path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: auto-select based on provider)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        required=True,
        choices=[10, 100, 1000],
        help="Number of opportunities (10=Stage A, 100=Stage B, 1000=Stage C)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="local",
        choices=["local", "gemini"],
        help="LLM provider (local=Ollama, gemini=Google)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: auto-select based on provider)",
    )

    args = parser.parse_args()

    # Auto-select output path based on provider
    if args.output is None:
        if args.provider == "local":
            output_path = Path("datasets/v1.0.0/diagnoses_local")
        else:
            output_path = Path("datasets/v1.0.0/diagnoses_real")
    else:
        output_path = args.output

    diagnoser = PilotDiagnoser(
        dataset_path=args.dataset,
        output_path=output_path,
        limit=args.limit,
        provider=args.provider,
        model=args.model,
    )

    diagnoser.diagnose()


if __name__ == "__main__":
    main()
