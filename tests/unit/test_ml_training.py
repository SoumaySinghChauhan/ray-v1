"""
Tests for ML model training, serialization, and reload.

CRITICAL: These tests ensure model artifacts are valid and reproducible.
"""

import pytest
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

from ml.baseline.baseline_model import HistoricalRecoveryRateBaseline


@pytest.fixture
def model_dir():
    """Get model directory."""
    return Path("ml/models/v1.0.0")


@pytest.fixture
def validation_data():
    """Load validation data for testing."""
    val_path = Path("datasets/v1.0.0/ml/validation_model_a_features.parquet")
    return pd.read_parquet(val_path)


def test_model_a_artifact_exists(model_dir):
    """Test that Model A artifact was saved."""
    model_path = model_dir / "model_a_calibrated.pkl"
    assert model_path.exists(), f"Model A artifact not found at {model_path}"


def test_model_b_artifact_exists(model_dir):
    """Test that Model B artifact was saved."""
    model_path = model_dir / "model_b_calibrated.pkl"
    assert model_path.exists(), f"Model B artifact not found at {model_path}"


def test_baseline_artifact_exists(model_dir):
    """Test that baseline artifact was saved."""
    baseline_path = model_dir / "baseline.pkl"
    assert baseline_path.exists(), f"Baseline artifact not found at {baseline_path}"


def test_training_metadata_exists(model_dir):
    """Test that training metadata was saved."""
    metadata_path = model_dir / "training_metadata_7c.json"
    assert metadata_path.exists(), f"Training metadata not found at {metadata_path}"


def test_model_a_can_be_loaded(model_dir):
    """Test that Model A can be loaded from pickle."""
    model_path = model_dir / "model_a_calibrated.pkl"

    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)

    assert 'model' in artifact
    assert 'features' in artifact
    assert 'validation_metrics' in artifact
    assert artifact['calibrated'] is True


def test_model_b_can_be_loaded(model_dir):
    """Test that Model B can be loaded from pickle."""
    model_path = model_dir / "model_b_calibrated.pkl"

    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)

    assert 'model' in artifact
    assert 'features' in artifact
    assert 'validation_metrics' in artifact
    assert artifact['calibrated'] is True


def test_baseline_can_be_loaded(model_dir):
    """Test that baseline can be loaded from pickle."""
    baseline_path = model_dir / "baseline.pkl"

    with open(baseline_path, 'rb') as f:
        baseline = pickle.load(f)

    assert isinstance(baseline, HistoricalRecoveryRateBaseline)
    assert baseline.threshold is not None
    assert baseline.cold_start_fallback is not None


def test_model_a_has_predict_proba(model_dir):
    """Test that Model A has predict_proba method."""
    model_path = model_dir / "model_a_calibrated.pkl"

    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)

    model = artifact['model']
    assert hasattr(model, 'predict_proba'), "Model A missing predict_proba method"


def test_model_b_has_predict_proba(model_dir):
    """Test that Model B has predict_proba method."""
    model_path = model_dir / "model_b_calibrated.pkl"

    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)

    model = artifact['model']
    assert hasattr(model, 'predict_proba'), "Model B missing predict_proba method"


def test_baseline_has_predict_proba(model_dir):
    """Test that baseline has predict_proba method."""
    baseline_path = model_dir / "baseline.pkl"

    with open(baseline_path, 'rb') as f:
        baseline = pickle.load(f)

    assert hasattr(baseline, 'predict_proba'), "Baseline missing predict_proba method"


def test_model_a_prediction_reproducibility(model_dir, validation_data):
    """Test that Model A predictions are reproducible."""
    model_path = model_dir / "model_a_calibrated.pkl"

    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)

    model = artifact['model']
    features = artifact['features']

    # Get features
    from ml.features.feature_manifest import get_model_a_features
    base_features = get_model_a_features()

    # Prepare data (same as training)
    X_val = validation_data[base_features].copy()
    categorical_features = ['payment_method', 'failure_class']
    X_val_encoded = pd.get_dummies(X_val, columns=categorical_features, drop_first=True)

    # Align with training features
    for col in features:
        if col not in X_val_encoded.columns:
            X_val_encoded[col] = 0
    X_val_encoded = X_val_encoded[features]

    # Predict twice
    proba_1 = model.predict_proba(X_val_encoded)[:, 1]
    proba_2 = model.predict_proba(X_val_encoded)[:, 1]

    # Should be identical
    np.testing.assert_array_equal(proba_1, proba_2)


def test_baseline_prediction_reproducibility(model_dir, validation_data):
    """Test that baseline predictions are reproducible."""
    baseline_path = model_dir / "baseline.pkl"

    with open(baseline_path, 'rb') as f:
        baseline = pickle.load(f)

    # Predict twice
    proba_1 = baseline.predict_proba(validation_data)
    proba_2 = baseline.predict_proba(validation_data)

    # Should be identical
    np.testing.assert_array_equal(proba_1, proba_2)


def test_model_a_produces_valid_probabilities(model_dir, validation_data):
    """Test that Model A produces valid probability values."""
    model_path = model_dir / "model_a_calibrated.pkl"

    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)

    model = artifact['model']
    features = artifact['features']

    # Prepare data
    from ml.features.feature_manifest import get_model_a_features
    base_features = get_model_a_features()

    X_val = validation_data[base_features].copy()
    categorical_features = ['payment_method', 'failure_class']
    X_val_encoded = pd.get_dummies(X_val, columns=categorical_features, drop_first=True)

    for col in features:
        if col not in X_val_encoded.columns:
            X_val_encoded[col] = 0
    X_val_encoded = X_val_encoded[features]

    # Predict
    proba = model.predict_proba(X_val_encoded)[:, 1]

    # Check valid probability range
    assert (proba >= 0).all(), "Probabilities must be >= 0"
    assert (proba <= 1).all(), "Probabilities must be <= 1"
    assert not np.isnan(proba).any(), "Probabilities contain NaN"
    assert not np.isinf(proba).any(), "Probabilities contain Inf"


def test_baseline_produces_valid_probabilities(model_dir, validation_data):
    """Test that baseline produces valid probability values."""
    baseline_path = model_dir / "baseline.pkl"

    with open(baseline_path, 'rb') as f:
        baseline = pickle.load(f)

    # Predict
    proba = baseline.predict_proba(validation_data)

    # Check valid probability range
    assert (proba >= 0).all(), "Probabilities must be >= 0"
    assert (proba <= 1).all(), "Probabilities must be <= 1"
    assert not np.isnan(proba).any(), "Probabilities contain NaN"
    assert not np.isinf(proba).any(), "Probabilities contain Inf"


def test_training_metadata_has_required_fields(model_dir):
    """Test that training metadata has all required fields."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Required fields
    required_fields = [
        'prompt',
        'dataset_version',
        'random_seed',
        'training_timestamp',
        'test_accessed',
        'python_version',
        'sklearn_version',
        'model_a',
        'model_b',
        'baseline',
    ]

    for field in required_fields:
        assert field in metadata, f"Missing required field: {field}"


def test_training_metadata_test_firewall(model_dir):
    """Test that training metadata confirms test firewall."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    assert metadata['test_accessed'] is False, "Test set was accessed during training!"


def test_model_a_is_calibrated(model_dir):
    """Test that Model A is marked as calibrated."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    assert metadata['model_a']['calibrated'] is True, "Model A should be calibrated"


def test_model_b_is_calibrated(model_dir):
    """Test that Model B is marked as calibrated."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    assert metadata['model_b']['calibrated'] is True, "Model B should be calibrated"


def test_baseline_metrics_are_reasonable(model_dir):
    """Test that baseline metrics are within reasonable ranges."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    baseline_metrics = metadata['baseline']['validation_metrics']

    # ROC-AUC should be > 0.5 (better than random)
    assert baseline_metrics['roc_auc'] > 0.5, "Baseline ROC-AUC should be > 0.5"

    # Brier score should be < 0.25 (baseline should be better than constant prediction)
    assert baseline_metrics['brier_score'] < 0.25, "Baseline Brier should be < 0.25"


def test_model_a_improves_over_baseline(model_dir):
    """Test that Model A improves over baseline."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    baseline_auc = metadata['baseline']['validation_metrics']['roc_auc']
    model_a_auc = metadata['model_a']['validation_metrics']['roc_auc']

    # Model A should be at least as good as baseline
    assert model_a_auc >= baseline_auc, "Model A should not be worse than baseline"


def test_model_b_status_is_trained(model_dir):
    """Test that Model B status indicates successful training."""
    import json

    metadata_path = model_dir / "training_metadata_7c.json"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    assert metadata['model_b']['status'] == 'TRAINED', "Model B should be successfully trained"


def test_model_artifacts_are_not_empty(model_dir):
    """Test that model artifacts are not empty files."""
    model_a_path = model_dir / "model_a_calibrated.pkl"
    model_b_path = model_dir / "model_b_calibrated.pkl"
    baseline_path = model_dir / "baseline.pkl"

    # Check file sizes
    assert model_a_path.stat().st_size > 100, "Model A artifact is too small (likely empty)"
    assert model_b_path.stat().st_size > 100, "Model B artifact is too small (likely empty)"
    assert baseline_path.stat().st_size > 100, "Baseline artifact is too small (likely empty)"
