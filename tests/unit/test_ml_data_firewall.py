"""
Tests for ML data firewall.

CRITICAL: These tests enforce that test set is NEVER accessed during training/validation.
"""

import pytest
import pandas as pd
from pathlib import Path

from ml.training.data_loader import DataLoader, TestSetAccessError


@pytest.fixture
def data_loader():
    """Create data loader for testing."""
    data_dir = Path("datasets/v1.0.0/ml")
    return DataLoader(data_dir)


def test_train_split_loads_successfully(data_loader):
    """Test that training split loads without error."""
    train_df = data_loader.load_train()

    assert len(train_df) > 0
    assert 'split' in train_df.columns
    assert (train_df['split'] == 'train').all()
    assert 'target' in train_df.columns


def test_validation_split_loads_successfully(data_loader):
    """Test that validation split loads without error."""
    val_df = data_loader.load_validation()

    assert len(val_df) > 0
    assert 'split' in val_df.columns
    assert (val_df['split'] == 'validation').all()
    assert 'target' in val_df.columns


def test_test_split_requires_explicit_access(data_loader):
    """
    CRITICAL TEST: Test set cannot be loaded without explicit flag.

    This prevents accidental test set access during model training.
    """
    # Should raise TestSetAccessError by default
    with pytest.raises(TestSetAccessError) as exc_info:
        data_loader.load_test()

    assert "Test set access denied" in str(exc_info.value)
    assert "Prompt 8" in str(exc_info.value)


def test_test_split_loads_with_explicit_permission(data_loader):
    """
    Test that test set CAN be loaded when explicitly allowed.

    This should ONLY happen during Prompt 8 (final evaluation).
    """
    test_df = data_loader.load_test(allow_test_access=True)

    assert len(test_df) > 0
    assert 'split' in test_df.columns
    assert (test_df['split'] == 'test').all()


def test_no_customer_overlap_train_validation(data_loader):
    """Test that train and validation splits have no customer overlap."""
    train_df = data_loader.load_train()
    val_df = data_loader.load_validation()

    train_customers = set(train_df['customer_id'].unique())
    val_customers = set(val_df['customer_id'].unique())

    overlap = train_customers & val_customers

    assert len(overlap) == 0, f"Found {len(overlap)} customers in both train and validation"


def test_no_opportunity_duplicates_within_splits(data_loader):
    """Test that each split has no duplicate opportunities."""
    train_df = data_loader.load_train()
    val_df = data_loader.load_validation()

    train_dupes = train_df['opportunity_id'].duplicated().sum()
    val_dupes = val_df['opportunity_id'].duplicated().sum()

    assert train_dupes == 0, f"Found {train_dupes} duplicate opportunities in train"
    assert val_dupes == 0, f"Found {val_dupes} duplicate opportunities in validation"


def test_split_row_counts_match_expected(data_loader):
    """Test that split sizes match expected 550/150/300."""
    validation_result = data_loader.validate_splits()

    # Note: These are opportunity counts, not customer counts
    # Actual row counts may vary slightly
    assert validation_result['train_customers'] == 550, \
        f"Expected 550 train customers, got {validation_result['train_customers']}"

    assert validation_result['validation_customers'] == 150, \
        f"Expected 150 validation customers, got {validation_result['validation_customers']}"


def test_target_column_exists_in_splits(data_loader):
    """Test that target column exists in all splits."""
    train_df = data_loader.load_train()
    val_df = data_loader.load_validation()

    assert 'target' in train_df.columns
    assert 'target' in val_df.columns

    # Check target is binary
    assert train_df['target'].isin([0, 1]).all()
    assert val_df['target'].isin([0, 1]).all()


def test_no_future_leakage_columns(data_loader):
    """Test that no future information columns are present."""
    train_df = data_loader.load_train()

    # Forbidden columns that would leak future information
    forbidden = [
        'recovered_at',
        'recovery_amount',
        'actual_outcome',
        'true_organic_recovery_probability',
        'true_payment_link_recovery_probability'
    ]

    present_forbidden = [col for col in forbidden if col in train_df.columns]

    assert len(present_forbidden) == 0, \
        f"Found forbidden columns with future information: {present_forbidden}"


def test_test_accessed_flag_tracks_access(data_loader):
    """Test that test access flag is properly tracked."""
    # Initially false
    assert data_loader._test_accessed is False

    # Load test with permission
    data_loader.load_test(allow_test_access=True)

    # Now true
    assert data_loader._test_accessed is True


def test_validate_splits_returns_correct_structure(data_loader):
    """Test that validate_splits returns expected keys."""
    result = data_loader.validate_splits()

    expected_keys = [
        'train_rows',
        'train_customers',
        'validation_rows',
        'validation_customers',
        'customer_overlap',
        'train_duplicates',
        'validation_duplicates',
        'test_accessed',
    ]

    for key in expected_keys:
        assert key in result, f"Missing key in validation result: {key}"

    # Should not have accessed test during validation
    assert result['test_accessed'] is False
