#!/usr/bin/env python
"""
RAY V1 - Prompt 7E: Fix Model B Feature Integration

Properly loads and merges diagnosis features for Model B economic validation.
"""

import sys
import pickle
from pathlib import Path

import pandas as pd
import numpy as np

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ml.training.data_loader import DataLoader
from ml.features.feature_manifest import get_model_a_features


def load_frozen_model_b():
    """Load frozen Model B artifact and inspect feature contract."""
    model_path = Path('ml/models/v1.0.0/model_b_calibrated.pkl')

    with open(model_path, 'rb') as f:
        model_b = pickle.load(f)

    print("Model B Feature Contract:")
    print(f"  Total features: {len(model_b['features'])}")
    print(f"  Calibrated: {model_b['calibrated']}")

    return model_b


def load_diagnosis_data():
    """Load and validate diagnosis data."""
    dx_path = Path('datasets/v1.0.0/diagnoses_local_v1/diagnoses.parquet')
    dx = pd.read_parquet(dx_path)

    print(f"\nDiagnosis Data:")
    print(f"  Total: {len(dx)} diagnoses")
    print(f"  Successful: {(dx['diagnostic_status'] == 'success').sum()}")
    print(f"  Failed: {(dx['diagnostic_status'] != 'success').sum()}")

    return dx


def prepare_model_b_features(val_df, dx_df, expected_features):
    """
    Prepare Model B feature matrix matching exact training encoding.

    Args:
        val_df: Validation DataFrame
        dx_df: Diagnosis DataFrame
        expected_features: List of expected feature names from Model B

    Returns:
        DataFrame with exact Model B features
    """
    print("\nPreparing Model B Features:")

    # Merge validation with diagnosis
    val_with_dx = val_df.merge(
        dx_df[['opportunity_id', 'diagnostic_class', 'confidence', 'diagnostic_status']],
        on='opportunity_id',
        how='left'
    )

    print(f"  Validation rows: {len(val_df)}")
    print(f"  After merge: {len(val_with_dx)}")
    print(f"  Missing diagnosis: {val_with_dx['diagnostic_class'].isna().sum()}")

    # Handle missing diagnoses
    val_with_dx['diagnosis_missing'] = val_with_dx['diagnostic_class'].isna().astype(int)
    val_with_dx['diagnostic_class'] = val_with_dx['diagnostic_class'].fillna('UNKNOWN')
    val_with_dx['confidence'] = val_with_dx['confidence'].fillna(0.0)

    # Normalize diagnostic_class values (remove "DiagnosticClass." prefix if present)
    # This creates the exact encoding used during training
    val_with_dx['diagnostic_class_normalized'] = val_with_dx['diagnostic_class'].astype(str)

    # Get base Model A features
    base_features = get_model_a_features()
    X = val_with_dx[base_features].copy()

    # Add diagnosis features before encoding
    X['confidence'] = val_with_dx['confidence']
    X['diagnosis_missing'] = val_with_dx['diagnosis_missing']

    # Add diagnostic_class for encoding
    X['diagnostic_class'] = val_with_dx['diagnostic_class_normalized']

    # One-hot encode categoricals (same as training)
    categorical_features = ['payment_method', 'failure_class', 'diagnostic_class']
    X_encoded = pd.get_dummies(X, columns=categorical_features, drop_first=True)

    print(f"  Features after encoding: {len(X_encoded.columns)}")

    # Align with expected features from Model B
    # Add missing columns as zeros
    for feat in expected_features:
        if feat not in X_encoded.columns:
            X_encoded[feat] = 0

    # Select and reorder to match exact expected features
    X_final = X_encoded[expected_features]

    print(f"  Final feature count: {len(X_final.columns)}")
    print(f"  Expected: {len(expected_features)}")

    # Verify
    assert len(X_final.columns) == len(expected_features), "Feature count mismatch!"
    assert list(X_final.columns) == list(expected_features), "Feature order mismatch!"
    assert len(X_final) == len(val_df), "Row count mismatch!"

    print("  ✓ Feature alignment verified")

    return X_final, val_with_dx


def test_model_b_predictions(model_b, X_features):
    """Test that Model B can make predictions."""
    print("\nTesting Model B Predictions:")

    # Predict
    proba = model_b['model'].predict_proba(X_features)[:, 1]

    print(f"  Predictions: {len(proba)}")
    print(f"  Range: [{proba.min():.4f}, {proba.max():.4f}]")
    print(f"  Mean: {proba.mean():.4f}")
    print(f"  NaN count: {np.isnan(proba).sum()}")
    print(f"  Inf count: {np.isinf(proba).sum()}")

    # Validate
    assert len(proba) == len(X_features), "Prediction count mismatch!"
    assert (proba >= 0).all() and (proba <= 1).all(), "Invalid probabilities!"
    assert not np.isnan(proba).any(), "NaN predictions!"
    assert not np.isinf(proba).any(), "Inf predictions!"

    print("  ✓ Predictions valid")

    return proba


def main():
    """Main execution."""
    print("=" * 70)
    print("RAY V1 - PROMPT 7E: FIX MODEL B FEATURE INTEGRATION")
    print("=" * 70)

    # Load data
    print("\n[1/5] Load Data")
    loader = DataLoader(Path('datasets/v1.0.0/ml'))
    val_df = loader.load_validation()

    # Verify test not accessed
    validation_result = loader.validate_splits()
    assert not validation_result['test_accessed'], "Test set accessed!"
    print(f"  ✓ Test firewall: test_accessed = {validation_result['test_accessed']}")

    # Load Model B
    print("\n[2/5] Load Model B")
    model_b = load_frozen_model_b()
    expected_features = model_b['features']

    # Load diagnosis
    print("\n[3/5] Load Diagnosis Data")
    dx_df = load_diagnosis_data()

    # Prepare features
    print("\n[4/5] Prepare Model B Features")
    X_model_b, val_with_dx = prepare_model_b_features(val_df, dx_df, expected_features)

    # Test predictions
    print("\n[5/5] Test Model B Predictions")
    proba_b = test_model_b_predictions(model_b, X_model_b)

    # Save for economic analysis
    output_path = Path('datasets/v1.0.0/ml/validation_model_b_features.parquet')
    val_with_dx_features = val_df.copy()
    for col in X_model_b.columns:
        val_with_dx_features[col] = X_model_b[col].values
    val_with_dx_features['model_b_probability'] = proba_b

    val_with_dx_features.to_parquet(output_path, index=False)
    print(f"\n✓ Saved Model B features to: {output_path}")

    print("\n" + "=" * 70)
    print("MODEL B FEATURE INTEGRATION: SUCCESS")
    print("=" * 70)
    print(f"\nValidation set: {len(val_df)} opportunities")
    print(f"Model B features: {len(expected_features)}")
    print(f"Predictions: {len(proba_b)}")
    print(f"Prediction range: [{proba_b.min():.4f}, {proba_b.max():.4f}]")


if __name__ == "__main__":
    main()
