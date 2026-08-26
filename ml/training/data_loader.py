"""
Data loader with strict test set firewall for RAY V1.

CRITICAL: Test set must NEVER be loaded during model training or selection.
"""

import pandas as pd
from pathlib import Path
from typing import Literal, Tuple
import warnings


class TestSetAccessError(Exception):
    """Raised when attempting to access test set during training."""
    pass


class DataLoader:
    """
    Data loader with enforced test set firewall.

    Test set can only be loaded with explicit allow_test_access=True flag,
    which should ONLY be set during final evaluation (Prompt 8).
    """

    def __init__(self, data_dir: Path):
        """
        Initialize data loader.

        Args:
            data_dir: Directory containing train/validation/test parquet files
        """
        self.data_dir = Path(data_dir)
        self._test_accessed = False

    def load_train(self) -> pd.DataFrame:
        """
        Load training set (550 customers).

        Returns:
            Training DataFrame with features and target
        """
        train_path = self.data_dir / "train_model_a_features.parquet"
        if not train_path.exists():
            raise FileNotFoundError(f"Training data not found: {train_path}")

        df = pd.read_parquet(train_path)

        # Validate split
        assert 'split' in df.columns, "Missing 'split' column"
        assert (df['split'] == 'train').all(), "Train file contains non-train rows"

        return df

    def load_validation(self) -> pd.DataFrame:
        """
        Load validation set (150 customers).

        Returns:
            Validation DataFrame with features and target
        """
        val_path = self.data_dir / "validation_model_a_features.parquet"
        if not val_path.exists():
            raise FileNotFoundError(f"Validation data not found: {val_path}")

        df = pd.read_parquet(val_path)

        # Validate split
        assert 'split' in df.columns, "Missing 'split' column"
        assert (df['split'] == 'validation').all(), "Validation file contains non-validation rows"

        return df

    def load_test(self, allow_test_access: bool = False) -> pd.DataFrame:
        """
        Load test set (300 customers).

        CRITICAL: This should ONLY be called during final evaluation (Prompt 8).

        Args:
            allow_test_access: Must be explicitly set to True to access test set.
                              Should ONLY be True during final evaluation.

        Returns:
            Test DataFrame with features and target

        Raises:
            TestSetAccessError: If allow_test_access is False
        """
        if not allow_test_access:
            raise TestSetAccessError(
                "Test set access denied. Test set should ONLY be loaded during "
                "final evaluation (Prompt 8). Set allow_test_access=True only "
                "when performing final test-set evaluation."
            )

        self._test_accessed = True
        warnings.warn(
            "WARNING: Test set has been accessed. This should ONLY happen during "
            "final evaluation. Model selection and hyperparameter tuning must use "
            "train/validation sets only.",
            category=UserWarning
        )

        test_path = self.data_dir / "test_model_a_features.parquet"
        if not test_path.exists():
            raise FileNotFoundError(f"Test data not found: {test_path}")

        df = pd.read_parquet(test_path)

        # Validate split
        assert 'split' in df.columns, "Missing 'split' column"
        assert (df['split'] == 'test').all(), "Test file contains non-test rows"

        return df

    def load_train_validation(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load both train and validation sets for model training.

        Returns:
            (train_df, validation_df) tuple
        """
        return self.load_train(), self.load_validation()

    def validate_splits(self) -> dict:
        """
        Validate data splits without accessing test labels.

        Returns:
            Dictionary with split validation results
        """
        train_df = self.load_train()
        val_df = self.load_validation()

        # Check customer non-overlap
        train_customers = set(train_df['customer_id'].unique())
        val_customers = set(val_df['customer_id'].unique())

        overlap = train_customers & val_customers

        # Check for duplicates
        train_dupes = train_df['opportunity_id'].duplicated().sum()
        val_dupes = val_df['opportunity_id'].duplicated().sum()

        return {
            'train_rows': len(train_df),
            'train_customers': len(train_customers),
            'validation_rows': len(val_df),
            'validation_customers': len(val_customers),
            'customer_overlap': len(overlap),
            'train_duplicates': train_dupes,
            'validation_duplicates': val_dupes,
            'test_accessed': self._test_accessed,
        }


def load_diagnosis_data(diagnosis_path: Path) -> pd.DataFrame:
    """
    Load local Ollama diagnosis data for Model B.

    Args:
        diagnosis_path: Path to diagnoses_pilot_100.parquet

    Returns:
        DataFrame with diagnosis features
    """
    if not diagnosis_path.exists():
        raise FileNotFoundError(f"Diagnosis data not found: {diagnosis_path}")

    df = pd.read_parquet(diagnosis_path)

    # Validate required columns
    required_cols = ['opportunity_id', 'diagnostic_class', 'confidence']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Diagnosis data missing required columns: {missing}")

    return df
