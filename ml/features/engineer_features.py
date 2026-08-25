#!/usr/bin/env python3
"""
Feature engineering for RAY V1 ML models.

CRITICAL: Only observable features. No hidden simulator variables.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
from typing import Literal

from simulator.generation.data_loaders import (
    load_observable_dataset,
    load_hidden_ground_truth,
)
from ml.features.feature_manifest import (
    validate_feature_columns,
    get_model_a_features,
    get_model_b_features,
)


class FeatureEngineer:
    """Engineer ML features from observable data."""

    def __init__(self, dataset_path: Path):
        """
        Initialize feature engineer.

        Args:
            dataset_path: Path to frozen dataset
        """
        self.dataset_path = dataset_path

    def engineer_features(
        self,
        split: Literal["train", "validation", "test"],
        include_target: bool = True,
        include_llm_features: bool = False,
    ) -> pd.DataFrame:
        """
        Engineer features for a specific split.

        Args:
            split: Data split to engineer
            include_target: Whether to include target variable
            include_llm_features: Whether to include LLM diagnostic features

        Returns:
            DataFrame with engineered features

        Raises:
            ValueError: If forbidden features detected
        """

        print(f"Engineering features for {split} split...")

        # Load observable data
        df_obs = load_observable_dataset(self.dataset_path, split=split)
        print(f"  Loaded {len(df_obs)} opportunities")

        # Create features
        df_features = self._create_observable_features(df_obs)

        # Add LLM features if requested
        if include_llm_features:
            df_features = self._add_llm_features(df_features, df_obs)

        # Add target if requested
        if include_target:
            df_features = self._add_target(df_features, df_obs, split)

        # Validate no forbidden features
        # Allow target in training data, but not as a model feature
        validate_feature_columns(
            df_features.columns.tolist(),
            allow_identifiers=True,
            allow_target=include_target
        )

        print(f"  ✓ Engineered {len(df_features.columns)} features")

        return df_features

    def _create_observable_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create observable features (Model A)."""

        features = pd.DataFrame(index=df.index)

        # Identifiers (for joining, not ML features)
        features["opportunity_id"] = df["opportunity_id"]
        features["customer_id"] = df["customer_id"]
        features["split"] = df["split"]
        features["simulated_day"] = df["simulated_day"]

        # Payment amount features
        features["amount"] = df["amount"]
        features["log_amount"] = np.log1p(df["amount"])

        # Amount relative to customer average
        features["amount_to_avg_ratio"] = np.where(
            df["avg_payment_amount"] > 0,
            df["amount"] / df["avg_payment_amount"],
            1.0  # Neutral if no history
        )

        # Payment method (categorical)
        features["payment_method"] = df["payment_method"]

        # Failure class (categorical)
        features["failure_class"] = df["failure_class"]

        # Customer history features
        features["historical_payment_count"] = df["historical_payment_count"]
        features["historical_success_count"] = df["historical_success_count"]
        features["historical_failure_count"] = df["historical_failure_count"]
        features["historical_recovery_count"] = df["historical_recovery_count"]
        features["historical_recovery_rate"] = df["historical_recovery_rate"]

        # Customer value features
        features["customer_lifetime_value"] = df["customer_lifetime_value"]
        features["log_customer_lifetime_value"] = np.log1p(df["customer_lifetime_value"])

        # Customer tenure
        features["days_since_first_payment"] = df["days_since_first_payment"]

        # Time since failure
        features["hours_since_failure"] = df["hours_since_failure"]

        return features

    def _add_llm_features(self, df_features: pd.DataFrame, df_obs: pd.DataFrame) -> pd.DataFrame:
        """Add LLM diagnostic features (Model B)."""

        # Load diagnosis data
        diagnoses_path = self.dataset_path / "diagnoses" / "diagnoses.parquet"

        if not diagnoses_path.exists():
            raise FileNotFoundError(
                f"Diagnosis data not found at {diagnoses_path}. "
                f"Run batch_diagnose.py first."
            )

        df_diag = pd.read_parquet(diagnoses_path)

        # Merge diagnosis data
        df_merged = df_features.merge(
            df_diag[["opportunity_id", "diagnostic_class", "confidence", "reason_codes"]],
            on="opportunity_id",
            how="left",
        )

        # Diagnostic class (categorical)
        df_merged["diagnostic_class"] = df_diag["diagnostic_class"]

        # Diagnostic confidence
        df_merged["diagnostic_confidence"] = df_diag["confidence"]

        # Reason code indicators (one-hot)
        df_merged["reason_code_temporary_failure"] = df_diag["reason_codes"].apply(
            lambda x: "TEMPORARY_FAILURE" in x if isinstance(x, list) else False
        )
        df_merged["reason_code_persistent_failure"] = df_diag["reason_codes"].apply(
            lambda x: "PERSISTENT_FAILURE" in x if isinstance(x, list) else False
        )
        df_merged["reason_code_strong_payment_history"] = df_diag["reason_codes"].apply(
            lambda x: "STRONG_PAYMENT_HISTORY" in x if isinstance(x, list) else False
        )
        df_merged["reason_code_high_recovery_history"] = df_diag["reason_codes"].apply(
            lambda x: "HIGH_RECOVERY_HISTORY" in x if isinstance(x, list) else False
        )

        return df_merged

    def _add_target(
        self,
        df_features: pd.DataFrame,
        df_obs: pd.DataFrame,
        split: str
    ) -> pd.DataFrame:
        """
        Add target variable from ground truth.

        Target is P(recovery | payment_link).

        CRITICAL: Target comes from independent simulator ground truth,
        NOT from model predictions or optimizer decisions.

        Args:
            df_features: Feature dataframe
            df_obs: Observable dataframe
            split: Data split

        Returns:
            Features with target added
        """

        # Load ground truth
        df_truth = load_hidden_ground_truth(self.dataset_path)

        # Merge ground truth to get true probabilities
        df_with_truth = df_features.merge(
            df_truth[["opportunity_id", "true_payment_link_recovery_probability"]],
            on="opportunity_id",
            how="left",
        )

        # Generate binary target by sampling from true probability
        # Use opportunity-specific seed for reproducibility
        np.random.seed(42)  # Base seed

        # For each opportunity, sample from its true probability
        targets = []
        for _, row in df_with_truth.iterrows():
            prob = row["true_payment_link_recovery_probability"]
            # Use opportunity index as additional seed component
            target = np.random.random() < prob
            targets.append(int(target))

        df_features["target"] = targets

        # Sanity check: target should be binary
        assert df_features["target"].isin([0, 1]).all()

        return df_features


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Engineer ML features")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/v1.0.0"),
        help="Dataset path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/v1.0.0/ml"),
        help="Output path",
    )
    parser.add_argument(
        "--include-llm",
        action="store_true",
        help="Include LLM diagnostic features (Model B)",
    )

    args = parser.parse_args()

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    engineer = FeatureEngineer(args.dataset)

    # Engineer features for each split
    for split in ["train", "validation", "test"]:
        df_features = engineer.engineer_features(
            split=split,
            include_target=True,
            include_llm_features=args.include_llm,
        )

        # Save
        model_type = "model_b" if args.include_llm else "model_a"
        output_path = args.output / f"{split}_{model_type}_features.parquet"
        df_features.to_parquet(output_path, index=False)

        print(f"  ✓ Saved to {output_path}")
        print()

    print("Feature engineering complete!")


if __name__ == "__main__":
    main()
