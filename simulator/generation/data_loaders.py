"""
Data loaders with strict observable/hidden separation.

CRITICAL: Production code must ONLY use load_observable_dataset().
Hidden data must NEVER be accessible to production decision logic.
"""

from pathlib import Path
from typing import Literal
import pandas as pd
import warnings


class DataLoadError(Exception):
    """Raised when data loading fails."""
    pass


def load_observable_dataset(
    dataset_path: Path,
    split: Literal["train", "validation", "test"] | None = None,
) -> pd.DataFrame:
    """
    Load OBSERVABLE opportunity data for ML training/inference.

    This is the ONLY loader that production/ML code should use.

    Args:
        dataset_path: Path to dataset directory (e.g., datasets/v1.0.0/)
        split: Optional filter for train/validation/test

    Returns:
        DataFrame with observable features only

    Raises:
        DataLoadError: If data cannot be loaded
    """

    opportunities_path = dataset_path / "observable" / "current_opportunities.parquet"

    if not opportunities_path.exists():
        raise DataLoadError(f"Observable opportunities not found: {opportunities_path}")

    try:
        df = pd.read_parquet(opportunities_path)
    except Exception as e:
        raise DataLoadError(f"Failed to load opportunities: {e}") from e

    # Validate no hidden columns leaked
    _validate_no_hidden_columns(df)

    # Filter by split if requested
    if split is not None:
        df = df[df["split"] == split].copy()

    return df


def load_historical_transactions(
    dataset_path: Path,
    customer_ids: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load historical transaction data.

    Args:
        dataset_path: Path to dataset directory
        customer_ids: Optional filter for specific customers

    Returns:
        DataFrame with historical transactions
    """

    transactions_path = dataset_path / "observable" / "historical_transactions.parquet"

    if not transactions_path.exists():
        raise DataLoadError(f"Historical transactions not found: {transactions_path}")

    try:
        df = pd.read_parquet(transactions_path)
    except Exception as e:
        raise DataLoadError(f"Failed to load transactions: {e}") from e

    # Filter by customers if requested
    if customer_ids is not None:
        df = df[df["customer_id"].isin(customer_ids)].copy()

    return df


def load_hidden_ground_truth(
    dataset_path: Path,
) -> pd.DataFrame:
    """
    Load HIDDEN ground truth data.

    WARNING: This function must ONLY be used by:
    - Simulator code
    - Evaluation code
    - Test code

    NEVER use this in:
    - Production decision logic
    - ML inference
    - Optimizer
    - Policy engine

    Args:
        dataset_path: Path to dataset directory

    Returns:
        DataFrame with hidden ground truth

    Raises:
        DataLoadError: If data cannot be loaded
    """

    # Warn if being called from production code
    _check_caller_is_evaluation()

    ground_truth_path = dataset_path / "hidden" / "ground_truth_outcomes.parquet"

    if not ground_truth_path.exists():
        raise DataLoadError(f"Ground truth not found: {ground_truth_path}")

    try:
        df = pd.read_parquet(ground_truth_path)
    except Exception as e:
        raise DataLoadError(f"Failed to load ground truth: {e}") from e

    return df


def load_customer_latent_state(
    dataset_path: Path,
) -> pd.DataFrame:
    """
    Load HIDDEN customer latent state.

    WARNING: Same restrictions as load_hidden_ground_truth().

    Args:
        dataset_path: Path to dataset directory

    Returns:
        DataFrame with customer latent traits
    """

    _check_caller_is_evaluation()

    latent_path = dataset_path / "hidden" / "customer_latent_state.parquet"

    if not latent_path.exists():
        raise DataLoadError(f"Customer latent state not found: {latent_path}")

    try:
        df = pd.read_parquet(latent_path)
    except Exception as e:
        raise DataLoadError(f"Failed to load customer latent state: {e}") from e

    return df


def load_dataset_manifest(dataset_path: Path) -> dict:
    """
    Load dataset manifest metadata.

    Args:
        dataset_path: Path to dataset directory

    Returns:
        Manifest dictionary
    """

    import json

    manifest_path = dataset_path / "metadata" / "dataset_manifest.json"

    if not manifest_path.exists():
        raise DataLoadError(f"Manifest not found: {manifest_path}")

    try:
        with open(manifest_path) as f:
            return json.load(f)
    except Exception as e:
        raise DataLoadError(f"Failed to load manifest: {e}") from e


def _validate_no_hidden_columns(df: pd.DataFrame) -> None:
    """
    Validate that DataFrame does not contain hidden columns.

    Raises DataLoadError if hidden columns are found.
    """

    hidden_column_patterns = [
        "true_organic_recovery_probability",
        "true_payment_link_recovery_probability",
        "scenario_id",
        "latent",
        "hidden",
        "payment_reliability",
        "recovery_affinity",
        "contact_responsiveness",
    ]

    found_hidden = []
    for col in df.columns:
        for pattern in hidden_column_patterns:
            if pattern.lower() in col.lower():
                found_hidden.append(col)

    if found_hidden:
        raise DataLoadError(
            f"Hidden columns found in observable data: {found_hidden}. "
            f"This violates the observable/hidden separation contract."
        )


def _check_caller_is_evaluation() -> None:
    """
    Check if caller is from evaluation/simulator code.

    Issues a warning if called from production code paths.
    """

    import inspect
    import sys

    # Get call stack
    stack = inspect.stack()

    # Check if any frame is from production paths
    production_paths = [
        "/optimizer/",
        "/policy/",
        "/integrations/",
        "/services/api/",
    ]

    for frame in stack:
        filename = frame.filename
        for prod_path in production_paths:
            if prod_path in filename:
                warnings.warn(
                    f"load_hidden_ground_truth() called from production code: {filename}. "
                    f"Hidden data must not be used in production decision logic.",
                    category=RuntimeWarning,
                    stacklevel=3,
                )
                return


# Public API
__all__ = [
    "load_observable_dataset",
    "load_historical_transactions",
    "load_hidden_ground_truth",
    "load_customer_latent_state",
    "load_dataset_manifest",
    "DataLoadError",
]
