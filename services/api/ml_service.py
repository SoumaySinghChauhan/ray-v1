"""
ML prediction service for RAY V1 operational endpoints.

Loads the FROZEN Model A artifact (ml/models/v1.0.0/model_a_calibrated.pkl)
exactly as produced by Prompt 7C. Never retrains, never recalibrates.
"""

import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from ml.features.feature_manifest import get_model_a_features

_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "ml" / "models" / "v1.0.0" / "model_a_calibrated.pkl"


@lru_cache(maxsize=1)
def _load_model_a() -> dict:
    """Load the frozen Model A artifact once per process."""
    with open(_MODEL_PATH, "rb") as f:
        return pickle.load(f)


def model_a_metadata() -> dict[str, Any]:
    """Expose model identity without loading it into the response body."""
    artifact = _load_model_a()
    return {
        "model_type": artifact["model_type"],
        "calibrated": artifact["calibrated"],
        "feature_count": len(artifact["features"]),
        "version": "1.0.0",
    }


def predict_recovery_probability(raw_features: dict[str, Any]) -> float:
    """
    Predict recovery probability for a single opportunity.

    Args:
        raw_features: dict with the 14 observable base feature values,
            including the two categorical fields (payment_method,
            failure_class) as raw strings.

    Returns:
        Calibrated probability in [0, 1].
    """
    artifact = _load_model_a()
    base_features = get_model_a_features()

    row = {f: raw_features[f] for f in base_features}
    X = pd.DataFrame([row])
    X_encoded = pd.get_dummies(X, columns=["payment_method", "failure_class"], drop_first=True)

    for col in artifact["features"]:
        if col not in X_encoded.columns:
            X_encoded[col] = 0
    X_encoded = X_encoded[artifact["features"]]

    proba = artifact["model"].predict_proba(X_encoded)[0, 1]
    return float(proba)
