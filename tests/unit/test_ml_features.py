"""
Tests for ML feature validation and integrity.
"""

import pytest
import pandas as pd
from pathlib import Path

from ml.features.feature_manifest import (
    get_model_a_features,
    get_model_b_features,
    validate_feature_columns,
    OBSERVABLE_FEATURES,
    LLM_DIAGNOSTIC_FEATURES,
    FORBIDDEN_FEATURE_PATTERNS
)
from ml.training.data_loader import DataLoader


@pytest.fixture
def data_loader():
    """Create data loader."""
    return DataLoader(Path("datasets/v1.0.0/ml"))


def test_model_a_features_are_observable_only():
    """Test that Model A contains only observable features."""
    model_a_features = get_model_a_features()

    # All Model A features should be in OBSERVABLE_FEATURES
    observable_names = [f.name for f in OBSERVABLE_FEATURES]

    for feature in model_a_features:
        assert feature in observable_names, \
            f"Model A feature '{feature}' not in observable feature list"


def test_model_b_features_include_llm_diagnosis():
    """Test that Model B includes LLM diagnosis features."""
    model_b_features = get_model_b_features()
    model_a_features = get_model_a_features()

    # Model B should have more features than Model A
    assert len(model_b_features) > len(model_a_features)

    # Model B should include all Model A features
    for feature in model_a_features:
        assert feature in model_b_features, \
            f"Model A feature '{feature}' missing from Model B"

    # Model B should include LLM features
    llm_feature_names = [f.name for f in LLM_DIAGNOSTIC_FEATURES]
    for feature in llm_feature_names:
        assert feature in model_b_features, \
            f"LLM feature '{feature}' missing from Model B"


def test_no_forbidden_patterns_in_model_a_features():
    """Test that Model A features don't contain forbidden patterns."""
    model_a_features = get_model_a_features()

    # Should not raise ValueError
    validate_feature_columns(
        model_a_features + ['opportunity_id', 'customer_id'],
        allow_identifiers=True,
        allow_target=False
    )


def test_forbidden_pattern_detection():
    """Test that forbidden patterns are detected."""
    # Should raise ValueError for forbidden patterns
    with pytest.raises(ValueError) as exc_info:
        validate_feature_columns(['true_organic_recovery_probability'])

    assert "Forbidden features detected" in str(exc_info.value)


def test_train_data_has_model_a_features(data_loader):
    """Test that training data contains all Model A features."""
    train_df = data_loader.load_train()
    model_a_features = get_model_a_features()

    missing_features = [f for f in model_a_features if f not in train_df.columns]

    assert len(missing_features) == 0, \
        f"Training data missing Model A features: {missing_features}"


def test_validation_data_has_model_a_features(data_loader):
    """Test that validation data contains all Model A features."""
    val_df = data_loader.load_validation()
    model_a_features = get_model_a_features()

    missing_features = [f for f in model_a_features if f not in val_df.columns]

    assert len(missing_features) == 0, \
        f"Validation data missing Model A features: {missing_features}"


def test_feature_types_are_valid():
    """Test that all features have valid feature_type."""
    all_features = OBSERVABLE_FEATURES + LLM_DIAGNOSTIC_FEATURES
    valid_types = ['numeric', 'categorical', 'boolean']

    for feature in all_features:
        assert feature.feature_type in valid_types, \
            f"Feature '{feature.name}' has invalid type: {feature.feature_type}"


def test_observable_features_are_decision_time_observable():
    """Test that all observable features are marked as decision-time observable."""
    for feature in OBSERVABLE_FEATURES:
        assert feature.observable_at_decision_time is True, \
            f"Observable feature '{feature.name}' not marked as decision-time observable"


def test_llm_features_are_decision_time_observable():
    """Test that LLM features are marked as decision-time observable."""
    for feature in LLM_DIAGNOSTIC_FEATURES:
        assert feature.observable_at_decision_time is True, \
            f"LLM feature '{feature.name}' not marked as decision-time observable"


def test_target_column_validation():
    """Test that target column can be validated when explicitly allowed."""
    # Should not raise when allow_target=True
    validate_feature_columns(['target', 'payment_link_recovered'], allow_target=True)

    # Should raise when allow_target=False
    with pytest.raises(ValueError):
        validate_feature_columns(['target'], allow_target=False)


def test_model_a_feature_count():
    """Test that Model A has expected number of features."""
    model_a_features = get_model_a_features()

    # Model A should have all observable features
    assert len(model_a_features) == len(OBSERVABLE_FEATURES)


def test_model_b_feature_count():
    """Test that Model B has expected number of features."""
    model_b_features = get_model_b_features()

    # Model B = Model A + LLM features
    expected_count = len(OBSERVABLE_FEATURES) + len(LLM_DIAGNOSTIC_FEATURES)
    assert len(model_b_features) == expected_count
