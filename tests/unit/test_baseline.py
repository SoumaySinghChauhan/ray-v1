"""Test baseline implementation."""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evaluation.baselines.baseline import BaselinePredictor


def test_baseline_predictor_initialization():
    """Test baseline predictor initialization."""
    # Without fallback
    baseline = BaselinePredictor()
    assert baseline.cold_start_fallback is None
    assert not baseline.is_fitted

    # With fallback
    baseline = BaselinePredictor(cold_start_fallback=0.3)
    assert baseline.cold_start_fallback == 0.3
    assert baseline.is_fitted


def test_baseline_predictor_fit():
    """Test baseline fitting."""
    # Create sample validation data
    df = pd.DataFrame({
        "historical_recovery_rate": [0.2, 0.3, 0.4, 0.5],
        "historical_failure_count": [5, 10, 8, 12],
    })

    baseline = BaselinePredictor()
    baseline.fit(df)

    assert baseline.is_fitted
    assert baseline.cold_start_fallback is not None

    # Should be mean of recovery rates
    expected = df["historical_recovery_rate"].mean()
    assert abs(baseline.cold_start_fallback - expected) < 0.01


def test_baseline_predictor_predict_proba():
    """Test baseline probability prediction."""
    df = pd.DataFrame({
        "historical_recovery_rate": [0.2, 0.3, 0.0],
        "historical_failure_count": [5, 10, 0],  # Last is cold start
    })

    baseline = BaselinePredictor(cold_start_fallback=0.25)

    predictions = baseline.predict_proba(df)

    # First two use historical rate
    assert predictions[0] == 0.2
    assert predictions[1] == 0.3

    # Last uses cold-start fallback
    assert predictions[2] == 0.25


def test_baseline_predictor_requires_fit():
    """Test that prediction requires fitting first."""
    baseline = BaselinePredictor()

    df = pd.DataFrame({
        "historical_recovery_rate": [0.2],
        "historical_failure_count": [5],
    })

    with pytest.raises(RuntimeError, match="not fitted"):
        baseline.predict_proba(df)


def test_baseline_calculate_score():
    """Test baseline score calculation."""
    df = pd.DataFrame({
        "baseline_probability": [0.2, 0.3, 0.4],
        "amount": [1000, 2000, 1500],
    })

    baseline = BaselinePredictor(cold_start_fallback=0.3)
    df_scored = baseline.calculate_score(df)

    assert "baseline_score" in df_scored.columns

    # Score = probability × amount
    assert df_scored["baseline_score"].iloc[0] == 0.2 * 1000
    assert df_scored["baseline_score"].iloc[1] == 0.3 * 2000
    assert df_scored["baseline_score"].iloc[2] == 0.4 * 1500


def test_baseline_to_dict():
    """Test baseline configuration export."""
    baseline = BaselinePredictor(cold_start_fallback=0.3)

    config = baseline.to_dict()

    assert config["baseline_type"] == "historical_recovery_rate"
    assert config["cold_start_fallback"] == 0.3
    assert config["is_fitted"] is True


def test_baseline_from_dict():
    """Test baseline loading from configuration."""
    config = {
        "cold_start_fallback": 0.35,
    }

    baseline = BaselinePredictor.from_dict(config)

    assert baseline.cold_start_fallback == 0.35
    assert baseline.is_fitted
