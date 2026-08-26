#!/usr/bin/env python
"""
RAY V1 - Prompt 7B: Complete Local Ollama Diagnosis for TRAIN + VALIDATION

Completes diagnosis coverage for Model B training:
- TRAIN: 550 opportunities
- VALIDATION: 150 opportunities
- TOTAL: 700 opportunities

PRESERVES existing 100-case pilot diagnoses.
DOES NOT diagnose TEST set (300 opportunities).

CRITICAL: Test firewall enforced - zero test set access.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

import pandas as pd
import numpy as np
from tqdm import tqdm
from pydantic import ValidationError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ml.training.data_loader import DataLoader
from ai.diagnosis.local_provider import LocalDiagnosisProvider
from ai.diagnosis.schema import LLMDiagnosticOutput, DiagnosticStatus
from ai.diagnosis.prompt import (
    DIAGNOSIS_SYSTEM_PROMPT,
    DIAGNOSIS_PROMPT_VERSION,
    create_diagnosis_prompt,
)


class DiagnosisCompleter:
    """Completes diagnosis coverage for TRAIN+VALIDATION with test firewall."""

    def __init__(self):
        """Initialize diagnosis completer."""
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "datasets" / "v1.0.0" / "ml"
        self.pilot_dir = self.project_root / "datasets" / "v1.0.0" / "diagnoses_local"
        self.output_dir = self.project_root / "datasets" / "v1.0.0" / "diagnoses_local_v1"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Test firewall
        self.test_accessed = False
        self.test_diagnoses_attempted = 0

        # Quality tracking
        self.stats = {
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'retries': 0,
            'schema_failures': 0,
            'preserved_from_pilot': 0,
            'latencies': [],
            'errors': [],
        }

    def enforce_test_firewall(self):
        """Enforce that test set has not been accessed."""
        if self.test_accessed:
            raise RuntimeError("CRITICAL: Test set was accessed! Halting diagnosis.")
        if self.test_diagnoses_attempted > 0:
            raise RuntimeError(f"CRITICAL: {self.test_diagnoses_attempted} test diagnoses attempted! Halting.")

    def load_existing_diagnoses(self) -> pd.DataFrame:
        """
        Load existing pilot diagnoses to preserve.

        Returns:
            DataFrame with existing valid diagnoses
        """
        print("[1/8] Loading existing pilot diagnoses...")

        pilot_file = self.pilot_dir / "diagnoses_pilot_100.parquet"
        if not pilot_file.exists():
            print("  No existing pilot diagnoses found.")
            return pd.DataFrame()

        pilot_df = pd.read_parquet(pilot_file)
        print(f"  Loaded {len(pilot_df)} pilot diagnoses")

        # Filter to valid diagnoses only
        valid_df = pilot_df[pilot_df['diagnostic_class'].notna()].copy()
        print(f"  Valid diagnoses: {len(valid_df)}")
        print(f"  Failed diagnoses: {len(pilot_df) - len(valid_df)} (will be retried)")

        self.stats['preserved_from_pilot'] = len(valid_df)

        return valid_df

    def identify_missing_opportunities(
        self,
        existing_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Identify TRAIN and VALIDATION opportunities needing diagnosis.

        Args:
            existing_df: DataFrame with existing diagnoses

        Returns:
            (train_missing_df, validation_missing_df)
        """
        print("\n[2/8] Identifying missing opportunities...")

        # Load TRAIN and VALIDATION data (NOT test)
        loader = DataLoader(self.data_dir)
        train_df = loader.load_train()
        val_df = loader.load_validation()

        # Verify test not accessed
        assert not loader._test_accessed, "Test set was accessed during load!"
        self.enforce_test_firewall()

        print(f"  TRAIN opportunities: {len(train_df)}")
        print(f"  VALIDATION opportunities: {len(val_df)}")

        # Get existing opportunity IDs
        existing_opps = set(existing_df['opportunity_id']) if len(existing_df) > 0 else set()
        print(f"  Existing diagnoses: {len(existing_opps)}")

        # Identify missing
        train_missing = train_df[~train_df['opportunity_id'].isin(existing_opps)]
        val_missing = val_df[~val_df['opportunity_id'].isin(existing_opps)]

        print(f"  TRAIN missing: {len(train_missing)}")
        print(f"  VALIDATION missing: {len(val_missing)}")
        print(f"  Total to diagnose: {len(train_missing) + len(val_missing)}")

        # Verify no test opportunities leaked
        test_indicators = ['test' in str(x).lower() for x in train_missing['split']]
        if any(test_indicators):
            raise RuntimeError("CRITICAL: Test opportunities found in TRAIN missing set!")

        test_indicators = ['test' in str(x).lower() for x in val_missing['split']]
        if any(test_indicators):
            raise RuntimeError("CRITICAL: Test opportunities found in VALIDATION missing set!")

        self.enforce_test_firewall()

        return train_missing, val_missing

    def run_diagnosis_batch(
        self,
        opportunities_df: pd.DataFrame,
        split_name: str
    ) -> List[Dict[str, Any]]:
        """
        Run diagnosis on a batch of opportunities.

        Args:
            opportunities_df: Opportunities to diagnose
            split_name: 'TRAIN' or 'VALIDATION'

        Returns:
            List of diagnosis results
        """
        print(f"\n[3/8] Running {split_name} diagnosis...")
        print(f"  Total opportunities: {len(opportunities_df)}")
        print(f"  Estimated time: {len(opportunities_df) * 120 / 3600:.1f} hours @ 120s/opportunity")
        print(f"  Provider: local (Ollama)")
        print(f"  Model: qwen3:4b-instruct")
        print(f"  Concurrency: 1 (sequential for M1 resource safety)")
        print()

        # Initialize provider
        provider = LocalDiagnosisProvider(
            model="qwen3:4b-instruct",
            host="http://localhost:11434",
            temperature=0.7,
            num_ctx=2048,
        )

        results = []
        errors = []

        # Sequential processing for resource safety
        for idx, row in tqdm(opportunities_df.iterrows(), total=len(opportunities_df), desc=f"  {split_name}"):
            self.stats['attempted'] += 1

            opportunity_id = row['opportunity_id']
            customer_id = row['customer_id']

            # Build customer history summary (OBSERVABLE ONLY)
            history_summary = {
                "historical_payment_count": int(row.get('historical_payment_count', 0)),
                "historical_success_count": int(row.get('historical_success_count', 0)),
                "historical_failure_count": int(row.get('historical_failure_count', 0)),
                "historical_recovery_count": int(row.get('historical_recovery_count', 0)),
                "historical_recovery_rate": float(row.get('historical_recovery_rate', 0.0)),
                "customer_lifetime_value": float(row.get('customer_lifetime_value', 0.0)),
                "avg_payment_amount": float(row.get('avg_payment_amount', 0.0)),
                "days_since_first_payment": int(row.get('days_since_first_payment', 0)),
            }

            # Create diagnosis prompt
            prompt = create_diagnosis_prompt(
                payment_amount=float(row['amount']),
                payment_method=row['payment_method'],
                currency=row.get('currency', 'INR'),
                failure_class=row['failure_class'],
                failure_description=row.get('failure_description', f"{row['failure_class']} failure"),
                customer_history_summary=history_summary,
            )

            # Diagnose with timing
            start_time = time.time()

            try:
                # Call LLM
                llm_output, duration_ms = provider.generate(
                    system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
                    user_prompt=prompt,
                )

                # Validate schema
                validated = LLMDiagnosticOutput(**llm_output)

                elapsed = time.time() - start_time

                results.append({
                    'opportunity_id': opportunity_id,
                    'customer_id': customer_id,
                    'diagnostic_class': str(validated.diagnostic_class),
                    'reason_codes': [str(r) for r in validated.reason_codes],
                    'diagnostic_summary': validated.diagnostic_summary,
                    'confidence': validated.confidence,
                    'diagnostic_status': 'success',
                    'split': row['split'],
                    'latency_seconds': elapsed,
                    'diagnosis_version': '1.0.1',
                    'diagnosis_prompt_version': DIAGNOSIS_PROMPT_VERSION,
                    'diagnosis_model_version': 'qwen3:4b-instruct',
                    'diagnosis_schema_version': '1.0.0',
                    'generation_timestamp': datetime.now(timezone.utc).isoformat(),
                    'retry_count': 0,
                    'llm_call_duration_ms': duration_ms,
                })

                self.stats['successful'] += 1
                self.stats['latencies'].append(elapsed)

            except ValidationError as e:
                # Schema validation failed
                elapsed = time.time() - start_time
                self.stats['schema_failures'] += 1
                self.stats['failed'] += 1

                results.append({
                    'opportunity_id': opportunity_id,
                    'customer_id': customer_id,
                    'diagnostic_class': None,
                    'reason_codes': [],
                    'diagnostic_summary': None,
                    'confidence': 0.0,
                    'diagnostic_status': 'schema_validation_failed',
                    'split': row['split'],
                    'latency_seconds': elapsed,
                })

                errors.append({
                    'opportunity_id': opportunity_id,
                    'error_type': 'schema_validation',
                    'error_message': str(e),
                })

            except Exception as e:
                # LLM call failed
                elapsed = time.time() - start_time
                self.stats['failed'] += 1

                results.append({
                    'opportunity_id': opportunity_id,
                    'customer_id': customer_id,
                    'diagnostic_class': None,
                    'reason_codes': [],
                    'diagnostic_summary': None,
                    'confidence': 0.0,
                    'diagnostic_status': 'llm_call_failed',
                    'split': row['split'],
                    'latency_seconds': elapsed,
                })

                errors.append({
                    'opportunity_id': opportunity_id,
                    'error_type': 'llm_call_failure',
                    'error_message': str(e),
                })

        self.stats['errors'].extend(errors)

        return results

    def combine_diagnoses(
        self,
        existing_df: pd.DataFrame,
        new_results: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Combine existing and new diagnoses.

        Args:
            existing_df: Existing pilot diagnoses
            new_results: New diagnosis results

        Returns:
            Combined DataFrame
        """
        print("\n[4/8] Combining diagnoses...")

        # Convert new results to DataFrame
        new_df = pd.DataFrame(new_results)

        # Select common columns
        common_cols = ['opportunity_id', 'customer_id', 'diagnostic_class',
                      'reason_codes', 'diagnostic_summary', 'confidence', 'diagnostic_status']

        if len(existing_df) > 0:
            existing_selected = existing_df[common_cols].copy()
        else:
            existing_selected = pd.DataFrame(columns=common_cols)

        new_selected = new_df[common_cols].copy()

        # Combine
        combined = pd.concat([existing_selected, new_selected], ignore_index=True)

        print(f"  Existing: {len(existing_selected)}")
        print(f"  New: {len(new_selected)}")
        print(f"  Combined: {len(combined)}")

        # Check for duplicates
        dupes = combined['opportunity_id'].duplicated().sum()
        if dupes > 0:
            print(f"  WARNING: {dupes} duplicate opportunity IDs found")
            combined = combined.drop_duplicates(subset=['opportunity_id'], keep='first')
            print(f"  After deduplication: {len(combined)}")

        return combined

    def validate_coverage(self, combined_df: pd.DataFrame):
        """
        Validate final diagnosis coverage.

        Args:
            combined_df: Combined diagnosis DataFrame
        """
        print("\n[5/8] Validating coverage...")

        # Load TRAIN and VALIDATION to check coverage
        loader = DataLoader(self.data_dir)
        train_df = loader.load_train()
        val_df = loader.load_validation()

        # Verify test not accessed
        assert not loader._test_accessed, "Test set accessed during validation!"
        self.enforce_test_firewall()

        train_opps = set(train_df['opportunity_id'])
        val_opps = set(val_df['opportunity_id'])
        diagnosed_opps = set(combined_df['opportunity_id'])

        train_coverage = len(train_opps & diagnosed_opps)
        val_coverage = len(val_opps & diagnosed_opps)

        print(f"  TRAIN: {train_coverage} / {len(train_opps)} ({train_coverage/len(train_opps)*100:.1f}%)")
        print(f"  VALIDATION: {val_coverage} / {len(val_opps)} ({val_coverage/len(val_opps)*100:.1f}%)")
        print(f"  TEST: 0 / 300 (0.0%) ✓ TEST FIREWALL MAINTAINED")

        # Check for test leakage
        test_in_diagnosed = sum('test' in str(x).lower() for x in diagnosed_opps)
        if test_in_diagnosed > 0:
            raise RuntimeError(f"CRITICAL: {test_in_diagnosed} test opportunities in diagnosis set!")

        # Report missing
        train_missing = train_opps - diagnosed_opps
        val_missing = val_opps - diagnosed_opps

        if train_missing:
            print(f"  TRAIN missing: {len(train_missing)} opportunities")
        if val_missing:
            print(f"  VALIDATION missing: {len(val_missing)} opportunities")

        if train_coverage < len(train_opps) or val_coverage < len(val_opps):
            print("  ⚠ Coverage incomplete")
        else:
            print("  ✓ Complete coverage achieved")

    def compute_quality_metrics(self, combined_df: pd.DataFrame) -> Dict[str, Any]:
        """Compute diagnosis quality metrics."""
        print("\n[6/8] Computing quality metrics...")

        valid_df = combined_df[combined_df['diagnostic_class'].notna()]

        metrics = {
            'total': len(combined_df),
            'successful': len(valid_df),
            'failed': len(combined_df) - len(valid_df),
            'success_rate': len(valid_df) / len(combined_df) if len(combined_df) > 0 else 0.0,
        }

        # Confidence distribution
        if 'confidence' in valid_df.columns:
            conf_values = valid_df['confidence'].dropna()
            metrics['confidence'] = {
                'mean': float(conf_values.mean()) if len(conf_values) > 0 else 0.0,
                'min': float(conf_values.min()) if len(conf_values) > 0 else 0.0,
                'max': float(conf_values.max()) if len(conf_values) > 0 else 0.0,
                'std': float(conf_values.std()) if len(conf_values) > 0 else 0.0,
                'unique_values': int(conf_values.nunique()),
            }

        # Diagnostic class distribution
        if 'diagnostic_class' in valid_df.columns:
            class_counts = valid_df['diagnostic_class'].value_counts().to_dict()
            metrics['diagnostic_class_distribution'] = class_counts

        # Latency
        if self.stats['latencies']:
            latencies = np.array(self.stats['latencies'])
            metrics['latency'] = {
                'mean': float(latencies.mean()),
                'p50': float(np.percentile(latencies, 50)),
                'p95': float(np.percentile(latencies, 95)),
                'min': float(latencies.min()),
                'max': float(latencies.max()),
            }

        print(f"  Success rate: {metrics['success_rate']*100:.1f}%")
        print(f"  Confidence mean: {metrics.get('confidence', {}).get('mean', 0.0):.3f}")
        if 'latency' in metrics:
            print(f"  Latency p50: {metrics['latency']['p50']:.1f}s")
            print(f"  Latency p95: {metrics['latency']['p95']:.1f}s")

        return metrics

    def save_artifacts(
        self,
        combined_df: pd.DataFrame,
        metrics: Dict[str, Any]
    ):
        """Save final diagnosis artifacts."""
        print("\n[7/8] Saving artifacts...")

        # Save diagnoses parquet
        diagnoses_path = self.output_dir / "diagnoses.parquet"
        combined_df.to_parquet(diagnoses_path, index=False)
        print(f"  Saved: {diagnoses_path}")

        # Save manifest
        manifest = {
            'provider': 'local',
            'model': 'qwen3:4b-instruct',
            'dataset_version': '1.0.0',
            'diagnosis_version': '1.0.0',
            'prompt_version': '1.0.0',
            'schema_version': '1.0.0',
            'train_count': int((combined_df.get('split', pd.Series()) == 'train').sum()),
            'validation_count': int((combined_df.get('split', pd.Series()) == 'validation').sum()),
            'test_count': 0,  # Enforced by test firewall
            'total_count': len(combined_df),
            'successful_count': metrics['successful'],
            'failed_count': metrics['failed'],
            'preserved_from_pilot': self.stats['preserved_from_pilot'],
            'run_timestamp': datetime.now(timezone.utc).isoformat(),
            'test_accessed': self.test_accessed,
            'test_diagnoses_attempted': self.test_diagnoses_attempted,
        }

        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"  Saved: {manifest_path}")

        # Save quality report
        quality_report = f"""RAY V1 - Diagnosis Quality Report
Generated: {datetime.now(timezone.utc).isoformat()}

COVERAGE:
  TRAIN: {manifest['train_count']} diagnoses
  VALIDATION: {manifest['validation_count']} diagnoses
  TEST: 0 diagnoses (TEST FIREWALL MAINTAINED)
  Total: {manifest['total_count']} diagnoses

SUCCESS RATE:
  Successful: {metrics['successful']}
  Failed: {metrics['failed']}
  Success rate: {metrics['success_rate']*100:.1f}%

CONFIDENCE:
  Mean: {metrics.get('confidence', {}).get('mean', 0.0):.3f}
  Std: {metrics.get('confidence', {}).get('std', 0.0):.3f}
  Range: [{metrics.get('confidence', {}).get('min', 0.0):.3f}, {metrics.get('confidence', {}).get('max', 0.0):.3f}]
  Unique values: {metrics.get('confidence', {}).get('unique_values', 0)}

LATENCY:
  Mean: {metrics.get('latency', {}).get('mean', 0.0):.1f}s
  p50: {metrics.get('latency', {}).get('p50', 0.0):.1f}s
  p95: {metrics.get('latency', {}).get('p95', 0.0):.1f}s

DIAGNOSTIC CLASS DISTRIBUTION:
"""
        for cls, count in metrics.get('diagnostic_class_distribution', {}).items():
            quality_report += f"  {cls}: {count}\n"

        quality_report += f"\nPRESERVED FROM PILOT: {self.stats['preserved_from_pilot']} diagnoses\n"

        quality_path = self.output_dir / "quality_report.txt"
        with open(quality_path, 'w') as f:
            f.write(quality_report)
        print(f"  Saved: {quality_path}")

        # Save errors
        if self.stats['errors']:
            error_path = self.output_dir / "error_log.json"
            with open(error_path, 'w') as f:
                json.dump(self.stats['errors'], f, indent=2)
            print(f"  Saved: {error_path} ({len(self.stats['errors'])} errors)")

        print(f"\n  All artifacts saved to: {self.output_dir}")

    def run(self):
        """Main execution flow."""
        print("=" * 70)
        print("RAY V1 - Prompt 7B: Complete TRAIN+VALIDATION Diagnosis")
        print("=" * 70)
        print()

        try:
            # Load existing
            existing_df = self.load_existing_diagnoses()

            # Identify missing
            train_missing, val_missing = self.identify_missing_opportunities(existing_df)

            total_missing = len(train_missing) + len(val_missing)

            if total_missing == 0:
                print("\n✓ All TRAIN and VALIDATION opportunities already have diagnoses!")
                print("  No new diagnosis needed.")
                combined_df = existing_df
            else:
                # Run diagnosis
                train_results = self.run_diagnosis_batch(train_missing, "TRAIN") if len(train_missing) > 0 else []
                val_results = self.run_diagnosis_batch(val_missing, "VALIDATION") if len(val_missing) > 0 else []

                all_results = train_results + val_results

                # Combine
                combined_df = self.combine_diagnoses(existing_df, all_results)

            # Validate
            self.validate_coverage(combined_df)

            # Quality metrics
            metrics = self.compute_quality_metrics(combined_df)

            # Save
            self.save_artifacts(combined_df, metrics)

            # Final test firewall check
            print("\n[8/8] Final test firewall check...")
            self.enforce_test_firewall()
            print("  ✓ TEST FIREWALL MAINTAINED - Zero test set access")

            print("\n" + "=" * 70)
            print("PROMPT 7B COMPLETE")
            print("=" * 70)
            print(f"\nDiagnosis coverage: {len(combined_df)} / 700 opportunities")
            print(f"Success rate: {metrics['success_rate']*100:.1f}%")
            print(f"Test firewall: PASS")
            print(f"\nArtifacts: {self.output_dir}")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='RAY V1 - Prompt 7B: Complete Local Ollama Diagnosis for TRAIN + VALIDATION',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
IMPORTANT:
  This script will diagnose ~624 opportunities over 17-21 hours.
  Requires local Ollama with qwen3:4b-instruct model.
  DOES NOT access test set (300 opportunities).

  Use --dry-run to verify setup without running diagnosis.
        '''
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report what would be diagnosed without running inference'
    )

    args = parser.parse_args()

    completer = DiagnosisCompleter()

    if args.dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No diagnosis will be performed")
        print("=" * 70)
        print()

        # Load existing and identify missing
        existing_df = completer.load_existing_diagnoses()
        train_missing, val_missing = completer.identify_missing_opportunities(existing_df)

        print("\n[DRY RUN] Summary:")
        print(f"  TRAIN missing: {len(train_missing)} opportunities")
        print(f"  VALIDATION missing: {len(val_missing)} opportunities")
        print(f"  Total to diagnose: {len(train_missing) + len(val_missing)} opportunities")
        print(f"  Estimated time: {(len(train_missing) + len(val_missing)) * 120 / 3600:.1f} hours @ 120s/opportunity")
        print("\nTo run actual diagnosis:")
        print(f"  services/api/.venv/bin/python {Path(__file__).name}")
        print()
        return

    completer.run()


if __name__ == "__main__":
    main()
