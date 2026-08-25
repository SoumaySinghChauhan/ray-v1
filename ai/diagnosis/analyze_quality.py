#!/usr/bin/env python3
"""
Analyze diagnosis quality.

Generates quality report for offline diagnosis results.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import json
from collections import Counter

from simulator.generation.data_loaders import load_observable_dataset


class DiagnosisQualityAnalyzer:
    """Analyze diagnosis quality and generate report."""

    def __init__(self, dataset_path: Path, diagnosis_path: Path):
        """
        Initialize analyzer.

        Args:
            dataset_path: Path to frozen dataset
            diagnosis_path: Path to diagnosis results
        """
        self.dataset_path = dataset_path
        self.diagnosis_path = diagnosis_path

    def analyze(self) -> dict:
        """
        Run quality analysis.

        Returns:
            Analysis results dictionary
        """

        print("=" * 70)
        print("DIAGNOSIS QUALITY ANALYSIS")
        print("=" * 70)
        print()

        # Load data
        df_opportunities = load_observable_dataset(self.dataset_path)
        df_diagnoses = pd.read_parquet(self.diagnosis_path / "diagnoses.parquet")

        with open(self.diagnosis_path / "diagnosis_manifest.json") as f:
            manifest = json.load(f)

        print(f"Opportunities: {len(df_opportunities)}")
        print(f"Diagnoses: {len(df_diagnoses)}")
        print()

        # Merge for comparison
        df_merged = pd.merge(
            df_opportunities,
            df_diagnoses,
            on="opportunity_id",
            suffixes=("_canonical", "_llm"),
        )

        # Analyses
        results = {
            "manifest": manifest,
            "diagnostic_class_distribution": self._analyze_diagnostic_class(df_diagnoses),
            "confidence_distribution": self._analyze_confidence(df_diagnoses),
            "reason_code_distribution": self._analyze_reason_codes(df_diagnoses),
            "status_distribution": self._analyze_status(df_diagnoses),
            "canonical_vs_llm": self._compare_classes(df_merged),
            "disagreement_examples": self._sample_disagreements(df_merged),
        }

        self._print_report(results)

        return results

    def _analyze_diagnostic_class(self, df: pd.DataFrame) -> dict:
        """Analyze diagnostic class distribution."""
        counts = df["diagnostic_class"].value_counts()
        return {
            "distribution": counts.to_dict(),
            "total": len(df),
        }

    def _analyze_confidence(self, df: pd.DataFrame) -> dict:
        """Analyze confidence distribution."""
        return {
            "mean": float(df["confidence"].mean()),
            "median": float(df["confidence"].median()),
            "std": float(df["confidence"].std()),
            "min": float(df["confidence"].min()),
            "max": float(df["confidence"].max()),
            "percentiles": {
                "25th": float(df["confidence"].quantile(0.25)),
                "50th": float(df["confidence"].quantile(0.50)),
                "75th": float(df["confidence"].quantile(0.75)),
                "90th": float(df["confidence"].quantile(0.90)),
            },
        }

    def _analyze_reason_codes(self, df: pd.DataFrame) -> dict:
        """Analyze reason code distribution."""
        # Flatten reason code lists
        all_codes = []
        for codes in df["reason_codes"]:
            all_codes.extend(codes)

        counts = Counter(all_codes)

        return {
            "total_uses": len(all_codes),
            "unique_codes": len(counts),
            "distribution": dict(counts.most_common()),
        }

    def _analyze_status(self, df: pd.DataFrame) -> dict:
        """Analyze diagnostic status distribution."""
        counts = df["diagnostic_status"].value_counts()
        return {
            "distribution": counts.to_dict(),
            "success_rate": float(counts.get("SUCCESS", 0) / len(df)),
        }

    def _compare_classes(self, df: pd.DataFrame) -> dict:
        """Compare canonical vs LLM diagnostic classes."""

        # Convert to same format for comparison
        df["canonical_class_upper"] = df["failure_class"].str.upper()

        # Count agreements and disagreements
        df["agrees"] = df["canonical_class_upper"] == df["diagnostic_class"]

        agreement_rate = df["agrees"].mean()
        disagreement_count = (~df["agrees"]).sum()

        # Confusion matrix
        confusion = pd.crosstab(
            df["canonical_class_upper"],
            df["diagnostic_class"],
            margins=True,
        )

        return {
            "agreement_rate": float(agreement_rate),
            "disagreement_count": int(disagreement_count),
            "confusion_matrix": confusion.to_dict(),
        }

    def _sample_disagreements(self, df: pd.DataFrame, n: int = 5) -> list:
        """Sample disagreement examples for inspection."""

        df["canonical_class_upper"] = df["failure_class"].str.upper()
        df_disagreements = df[df["canonical_class_upper"] != df["diagnostic_class"]]

        if len(df_disagreements) == 0:
            return []

        # Sample up to n disagreements
        sample_size = min(n, len(df_disagreements))
        sample = df_disagreements.sample(n=sample_size, random_state=42)

        examples = []
        for _, row in sample.iterrows():
            examples.append({
                "opportunity_id": row["opportunity_id"],
                "canonical_class": row["failure_class"],
                "llm_diagnostic_class": row["diagnostic_class"],
                "failure_description": row["failure_description"],
                "diagnostic_summary": row["diagnostic_summary"],
                "confidence": float(row["confidence"]),
            })

        return examples

    def _print_report(self, results: dict):
        """Print human-readable report."""

        print("DIAGNOSTIC CLASS DISTRIBUTION")
        print("-" * 70)
        for cls, count in results["diagnostic_class_distribution"]["distribution"].items():
            pct = 100 * count / results["diagnostic_class_distribution"]["total"]
            print(f"  {cls:30} {count:5} ({pct:5.1f}%)")
        print()

        print("CONFIDENCE DISTRIBUTION")
        print("-" * 70)
        conf = results["confidence_distribution"]
        print(f"  Mean:     {conf['mean']:.3f}")
        print(f"  Median:   {conf['median']:.3f}")
        print(f"  Std Dev:  {conf['std']:.3f}")
        print(f"  Range:    [{conf['min']:.3f}, {conf['max']:.3f}]")
        print(f"  25th %ile: {conf['percentiles']['25th']:.3f}")
        print(f"  75th %ile: {conf['percentiles']['75th']:.3f}")
        print(f"  90th %ile: {conf['percentiles']['90th']:.3f}")
        print()

        print("REASON CODE DISTRIBUTION (Top 10)")
        print("-" * 70)
        reason_codes = results["reason_code_distribution"]["distribution"]
        for code, count in list(reason_codes.items())[:10]:
            print(f"  {code:30} {count:5}")
        print()

        print("DIAGNOSTIC STATUS")
        print("-" * 70)
        for status, count in results["status_distribution"]["distribution"].items():
            print(f"  {status:30} {count:5}")
        print(f"  Success rate: {results['status_distribution']['success_rate']:.1%}")
        print()

        print("CANONICAL vs LLM DIAGNOSTIC CLASS")
        print("-" * 70)
        print(f"  Agreement rate: {results['canonical_vs_llm']['agreement_rate']:.1%}")
        print(f"  Disagreements: {results['canonical_vs_llm']['disagreement_count']}")
        print()

        if results["disagreement_examples"]:
            print("DISAGREEMENT EXAMPLES (Sample)")
            print("-" * 70)
            for i, ex in enumerate(results["disagreement_examples"], 1):
                print(f"\nExample {i}:")
                print(f"  Opportunity: {ex['opportunity_id']}")
                print(f"  Canonical: {ex['canonical_class']}")
                print(f"  LLM: {ex['llm_diagnostic_class']}")
                print(f"  Confidence: {ex['confidence']:.2f}")
                print(f"  Description: {ex['failure_description'][:80]}...")
                print(f"  LLM Summary: {ex['diagnostic_summary'][:80]}...")
            print()

        print("=" * 70)


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Analyze diagnosis quality")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/v1.0.0"),
        help="Dataset path",
    )
    parser.add_argument(
        "--diagnoses",
        type=Path,
        default=Path("datasets/v1.0.0/diagnoses"),
        help="Diagnoses path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path for JSON results",
    )

    args = parser.parse_args()

    analyzer = DiagnosisQualityAnalyzer(
        dataset_path=args.dataset,
        diagnosis_path=args.diagnoses,
    )

    results = analyzer.analyze()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Saved results to {args.output}")


if __name__ == "__main__":
    main()
