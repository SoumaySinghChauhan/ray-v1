#!/usr/bin/env python3
"""
Baseline threshold tuning.

Select threshold that maximizes validation net expected recovery
under daily capacity constraints.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import pandas as pd
import numpy as np
from typing import Any

from config import get_config
from evaluation.baselines.baseline import BaselinePredictor


class BaselineThresholdTuner:
    """Tune baseline threshold on validation set."""

    def __init__(self, config):
        """Initialize tuner."""
        self.config = config
        self.baseline = BaselinePredictor()

    def tune(
        self,
        df_train: pd.DataFrame,
        df_validation: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Tune baseline threshold on validation set.

        Args:
            df_train: Training data (for fitting baseline)
            df_validation: Validation data (for threshold selection)

        Returns:
            Tuning results including best threshold
        """

        print("=" * 70)
        print("BASELINE THRESHOLD TUNING")
        print("=" * 70)
        print()

        # Fit baseline on train data
        print("Fitting baseline...")
        self.baseline.fit(df_train)
        print()

        # Predict on validation
        print("Predicting on validation...")
        df_val = df_validation.copy()
        df_val["baseline_probability"] = self.baseline.predict_proba(df_val)
        df_val = self.baseline.calculate_score(df_val, "baseline_probability")
        print()

        # Tune threshold
        print("Tuning threshold...")
        candidate_thresholds = self._generate_candidate_thresholds(df_val)

        results = []
        for threshold in candidate_thresholds:
            metric = self._evaluate_threshold(df_val, threshold)
            results.append({
                "threshold": threshold,
                **metric,
            })

        df_results = pd.DataFrame(results)

        # Select best threshold by net recovery
        best_idx = df_results["net_recovery"].idxmax()
        best_result = df_results.iloc[best_idx]

        print(f"\nBest threshold: {best_result['threshold']:.2f}")
        print(f"  Actions selected: {best_result['actions_selected']}")
        print(f"  Net recovery: ₹{best_result['net_recovery']:.2f}")
        print(f"  Recovery rate: {best_result['recovery_rate']:.2%}")
        print()

        return {
            "best_threshold": float(best_result["threshold"]),
            "best_metric_name": "net_recovery",
            "best_metric_value": float(best_result["net_recovery"]),
            "validation_actions_selected": int(best_result["actions_selected"]),
            "validation_recovery_rate": float(best_result["recovery_rate"]),
            "all_results": df_results.to_dict(orient="records"),
            "baseline_config": self.baseline.to_dict(),
        }

    def _generate_candidate_thresholds(self, df: pd.DataFrame) -> list[float]:
        """Generate candidate thresholds to test."""

        scores = df["baseline_score"].values

        # Use percentiles as candidates
        percentiles = np.arange(0, 100, 5)
        thresholds = np.percentile(scores, percentiles)

        # Add min and max
        thresholds = np.concatenate([[scores.min()], thresholds, [scores.max()]])

        # Remove duplicates and sort
        thresholds = np.unique(thresholds)

        return thresholds.tolist()

    def _evaluate_threshold(
        self,
        df: pd.DataFrame,
        threshold: float
    ) -> dict[str, float]:
        """
        Evaluate a threshold under daily capacity constraints.

        Args:
            df: Validation dataframe with scores and targets
            threshold: Score threshold to test

        Returns:
            Evaluation metrics
        """

        daily_capacity = self.config.recovery.max_actions_per_day

        # Filter by threshold
        df_eligible = df[df["baseline_score"] >= threshold].copy()

        # Process each simulated day independently
        total_actions = 0
        total_recovered = 0.0

        for day in sorted(df_eligible["simulated_day"].unique()):
            day_opportunities = df_eligible[df_eligible["simulated_day"] == day]

            # Sort by score descending
            day_opportunities = day_opportunities.sort_values(
                "baseline_score",
                ascending=False
            )

            # Select top N
            selected = day_opportunities.head(daily_capacity)

            total_actions += len(selected)

            # Use actual target for recovery calculation
            # (In real evaluation, this would be the outcome)
            total_recovered += float(
                (selected["target"] * selected["amount"]).sum()
            )

        # Calculate metrics
        recovery_rate = (
            total_recovered / df_eligible["amount"].sum()
            if len(df_eligible) > 0
            else 0.0
        )

        return {
            "actions_selected": total_actions,
            "net_recovery": total_recovered,
            "recovery_rate": recovery_rate,
        }


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Tune baseline threshold")
    parser.add_argument(
        "--train",
        type=Path,
        default=Path("datasets/v1.0.0/ml/train_model_a_features.parquet"),
        help="Training features",
    )
    parser.add_argument(
        "--validation",
        type=Path,
        default=Path("datasets/v1.0.0/ml/validation_model_a_features.parquet"),
        help="Validation features",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/baselines/v1.0.0"),
        help="Output path",
    )

    args = parser.parse_args()

    # Load config
    config = get_config()

    # Load data
    print("Loading data...")
    df_train = pd.read_parquet(args.train)
    df_validation = pd.read_parquet(args.validation)
    print(f"  Train: {len(df_train)} opportunities")
    print(f"  Validation: {len(df_validation)} opportunities")
    print()

    # Tune
    tuner = BaselineThresholdTuner(config)
    results = tuner.tune(df_train, df_validation)

    # Save results
    args.output.mkdir(parents=True, exist_ok=True)

    output_path = args.output / "threshold.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved threshold to {output_path}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
