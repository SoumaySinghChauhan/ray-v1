"""Test feature engineering."""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.features.feature_manifest import (
    validate_feature_columns,
    get_model_a_features,
    get_model_b_features,
    OBSERVABLE_FEATURES,
    LLM_DIAGNOSTIC_FEATURES,
)


def test_observable_features_documented():
    """Test that observable features are documented."""
    assert len(OBSERVABLE_FEATURES) > 0

    for feature in OBSERVABLE_FEATURES:
        assert feature.name
        assert feature.source
        assert feature.observable_at_decision_time is True
        assert feature.allowed_for_model is True
        assert feature.feature_type in ["numeric", "categorical", "boolean"]


def test_llm_features_documented():
    """Test that LLM features are documented."""
    assert len(LLM_DIAGNOSTIC_FEATURES) > 0

    for feature in LLM_DIAGNOSTIC_FEATURES:
        assert feature.name
        assert feature.source
        assert feature.observable_at_decision_time is True


def test_validate_feature_columns_allows_safe():
    """Test that safe features pass validation."""
    safe_columns = [
        "amount",
        "payment_method",
        "historical_recovery_rate",
        "diagnostic_class",
    ]

    # Should not raise
    validate_feature_columns(safe_columns, allow_identifiers=True, allow_target=False)


def test_validate_feature_columns_rejects_forbidden():
    """Test that forbidden features are rejected."""

    # Hidden ground truth
    with pytest.raises(ValueError, match="Forbidden features"):
        validate_feature_columns(
            ["amount", "true_organic_recovery_probability"],
            allow_identifiers=True,
            allow_target=False,
        )

    # Scenario ID
    with pytest.raises(ValueError, match="Forbidden features"):
        validate_feature_columns(
            ["amount", "scenario_id"],
            allow_identifiers=True,
            allow_target=False,
        )

    # Latent variable
    with pytest.raises(ValueError, match="Forbidden features"):
        validate_feature_columns(
            ["amount", "customer_recovery_affinity"],
            allow_identifiers=True,
            allow_target=False,
        )


def test_validate_feature_columns_allows_target_when_enabled():
    """Test that target is allowed when allow_target=True."""
    columns = ["amount", "target"]

    # Should not raise with allow_target=True
    validate_feature_columns(columns, allow_identifiers=True, allow_target=True)

    # Should raise with allow_target=False
    with pytest.raises(ValueError, match="Forbidden features"):
        validate_feature_columns(columns, allow_identifiers=True, allow_target=False)


def test_model_a_features():
    """Test Model A feature list."""
    features = get_model_a_features()

    assert len(features) > 0
    assert "amount" in features
    assert "historical_recovery_rate" in features

    # Should not include LLM features
    assert "diagnostic_class" not in features
    assert "diagnostic_confidence" not in features


def test_model_b_features():
    """Test Model B feature list."""
    features = get_model_b_features()

    assert len(features) > len(get_model_a_features())

    # Should include observable features
    assert "amount" in features
    assert "historical_recovery_rate" in features

    # Should include LLM features
    assert "diagnostic_class" in features
    assert "diagnostic_confidence" in features


def test_feature_manifest_no_hidden_features():
    """Test that feature manifest doesn't include hidden variables."""
    all_features = OBSERVABLE_FEATURES + LLM_DIAGNOSTIC_FEATURES

    forbidden_patterns = [
        "true_organic",
        "true_payment_link",
        "scenario_id",
        "latent",
    ]

    for feature in all_features:
        name_lower = feature.name.lower()
        source_lower = feature.source.lower()

        for pattern in forbidden_patterns:
            assert pattern not in name_lower, \
                f"Feature {feature.name} contains forbidden pattern {pattern}"
            assert pattern not in source_lower, \
                f"Feature source {feature.source} contains forbidden pattern {pattern}"
