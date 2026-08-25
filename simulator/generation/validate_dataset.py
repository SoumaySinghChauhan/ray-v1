#!/usr/bin/env python3
"""
Dataset validation script.

Validates that generated dataset meets all requirements.
Fails loudly if any validation check fails.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from decimal import Decimal

from config import get_config
from simulator.generation.data_loaders import (
    load_observable_dataset,
    load_hidden_ground_truth,
    load_customer_latent_state,
    load_dataset_manifest,
)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class DatasetValidator:
    """Validate generated dataset."""

    def __init__(self, dataset_path: Path):
        """Initialize validator."""
        self.dataset_path = dataset_path
        self.config = get_config()

    def validate(self) -> None:
        """Run all validation checks."""

        print("=" * 70)
        print("DATASET VALIDATION")
        print("=" * 70)
        print(f"Dataset: {self.dataset_path}")
        print()

        checks = [
            ("Manifest exists", self._validate_manifest_exists),
            ("Observable opportunities", self._validate_opportunities),
            ("Historical transactions", self._validate_historical_transactions),
            ("Data splits", self._validate_splits),
            ("Customer uniqueness", self._validate_customer_uniqueness),
            ("Simulated days", self._validate_simulated_days),
            ("Failure classes", self._validate_failure_classes),
            ("Amount ranges", self._validate_amount_ranges),
            ("Hidden/observable separation", self._validate_hidden_separation),
            ("Ground truth validity", self._validate_ground_truth),
        ]

        passed = 0
        failed = 0

        for check_name, check_fn in checks:
            try:
                check_fn()
                print(f"  ✓ {check_name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {check_name}: {e}")
                failed += 1

        print()
        print("=" * 70)

        if failed > 0:
            print(f"VALIDATION FAILED: {failed}/{len(checks)} checks failed")
            print("=" * 70)
            sys.exit(1)
        else:
            print(f"VALIDATION PASSED: {passed}/{len(checks)} checks passed")
            print("=" * 70)

    def _validate_manifest_exists(self):
        """Check manifest exists and is valid."""
        manifest = load_dataset_manifest(self.dataset_path)

        required_fields = [
            "dataset_version",
            "simulation_version",
            "customer_count",
            "current_opportunity_count",
        ]

        for field in required_fields:
            if field not in manifest:
                raise ValidationError(f"Manifest missing field: {field}")

    def _validate_opportunities(self):
        """Validate opportunity count and structure."""
        df = load_observable_dataset(self.dataset_path)

        expected_count = self.config.simulator.current_opportunities

        if len(df) != expected_count:
            raise ValidationError(
                f"Expected {expected_count} opportunities, found {len(df)}"
            )

        required_columns = [
            "opportunity_id",
            "customer_id",
            "amount",
            "failure_class",
            "simulated_day",
            "split",
            "historical_recovery_rate",
        ]

        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValidationError(f"Missing columns: {missing}")

    def _validate_historical_transactions(self):
        """Validate historical transaction counts."""
        from simulator.generation.data_loaders import load_historical_transactions

        df = load_historical_transactions(self.dataset_path)

        if df.empty:
            raise ValidationError("No historical transactions found")

        # Group by customer and check transaction counts
        counts = df.groupby("customer_id").size()

        min_count = self.config.simulator.historical_transactions_min
        max_count = self.config.simulator.historical_transactions_max

        below_min = (counts < min_count).sum()
        above_max = (counts > max_count).sum()

        if below_min > 0:
            raise ValidationError(f"{below_min} customers have < {min_count} transactions")

        if above_max > 0:
            raise ValidationError(f"{above_max} customers have > {max_count} transactions")

    def _validate_splits(self):
        """Validate train/validation/test splits."""
        df = load_observable_dataset(self.dataset_path)

        train = df[df["split"] == "train"]
        val = df[df["split"] == "validation"]
        test = df[df["split"] == "test"]

        expected_train = self.config.simulator.train_customers
        expected_val = self.config.simulator.validation_customers
        expected_test = self.config.simulator.test_customers

        if len(train) != expected_train:
            raise ValidationError(f"Expected {expected_train} train, found {len(train)}")

        if len(val) != expected_val:
            raise ValidationError(f"Expected {expected_val} validation, found {len(val)}")

        if len(test) != expected_test:
            raise ValidationError(f"Expected {expected_test} test, found {len(test)}")

    def _validate_customer_uniqueness(self):
        """Validate exactly one opportunity per customer."""
        df = load_observable_dataset(self.dataset_path)

        duplicates = df["customer_id"].duplicated().sum()

        if duplicates > 0:
            raise ValidationError(
                f"Found {duplicates} duplicate customers (multiple opportunities per customer)"
            )

        # Validate no customer appears in multiple splits
        train = set(df[df["split"] == "train"]["customer_id"])
        val = set(df[df["split"] == "validation"]["customer_id"])
        test = set(df[df["split"] == "test"]["customer_id"])

        train_val_overlap = train & val
        train_test_overlap = train & test
        val_test_overlap = val & test

        if train_val_overlap:
            raise ValidationError(f"Train/val overlap: {len(train_val_overlap)} customers")

        if train_test_overlap:
            raise ValidationError(f"Train/test overlap: {len(train_test_overlap)} customers")

        if val_test_overlap:
            raise ValidationError(f"Val/test overlap: {len(val_test_overlap)} customers")

    def _validate_simulated_days(self):
        """Validate simulated day distribution."""
        df = load_observable_dataset(self.dataset_path)

        expected_days = self.config.simulator.simulation_days

        unique_days = df["simulated_day"].unique()

        if len(unique_days) != expected_days:
            raise ValidationError(
                f"Expected {expected_days} unique days, found {len(unique_days)}"
            )

        if df["simulated_day"].min() != 1:
            raise ValidationError(f"Simulated days should start at 1")

        if df["simulated_day"].max() != expected_days:
            raise ValidationError(f"Simulated days should end at {expected_days}")

    def _validate_failure_classes(self):
        """Validate failure classes."""
        df = load_observable_dataset(self.dataset_path)

        valid_classes = [
            "soft_decline",
            "hard_decline",
            "authentication_failure",
            "gateway_error",
            "unknown",
        ]

        invalid = df[~df["failure_class"].isin(valid_classes)]

        if not invalid.empty:
            invalid_classes = invalid["failure_class"].unique()
            raise ValidationError(f"Invalid failure classes: {invalid_classes}")

    def _validate_amount_ranges(self):
        """Validate payment amounts."""
        df = load_observable_dataset(self.dataset_path)

        max_amount = float(self.config.simulator.payment_amount_max)

        if (df["amount"] <= 0).any():
            raise ValidationError("Found non-positive amounts")

        if (df["amount"] > max_amount).any():
            raise ValidationError(f"Found amounts exceeding max ({max_amount})")

    def _validate_hidden_separation(self):
        """Validate hidden/observable separation."""
        df_obs = load_observable_dataset(self.dataset_path)

        # Check no hidden columns in observable data
        hidden_patterns = [
            "true_organic",
            "true_payment_link",
            "scenario_id",
            "latent",
        ]

        found_hidden = []
        for col in df_obs.columns:
            for pattern in hidden_patterns:
                if pattern in col.lower():
                    found_hidden.append(col)

        if found_hidden:
            raise ValidationError(f"Hidden columns in observable data: {found_hidden}")

    def _validate_ground_truth(self):
        """Validate ground truth probabilities."""
        df_truth = load_hidden_ground_truth(self.dataset_path)

        # Check probabilities are in [0, 1]
        if not ((df_truth["true_organic_recovery_probability"] >= 0) &
                (df_truth["true_organic_recovery_probability"] <= 1)).all():
            raise ValidationError("Organic probabilities outside [0, 1]")

        if not ((df_truth["true_payment_link_recovery_probability"] >= 0) &
                (df_truth["true_payment_link_recovery_probability"] <= 1)).all():
            raise ValidationError("Payment link probabilities outside [0, 1]")


def main():
    """Main entry point."""

    dataset_path = Path("datasets/v1.0.0")

    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        print("Run generate_world.py first.")
        sys.exit(1)

    validator = DatasetValidator(dataset_path)
    validator.validate()


if __name__ == "__main__":
    main()
