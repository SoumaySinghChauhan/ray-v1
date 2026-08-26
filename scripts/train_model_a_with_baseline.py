#!/usr/bin/env python
"""
RAY V1 - Prompt 7A: Train Model A and Baseline

Trains Model A (observable features only) and validates against frozen baseline.

DOES NOT train Model B due to insufficient diagnosis coverage (100/700 opportunities).
DOES NOT evaluate on test set (reserved for Prompt 8).
"""

import sys
import json
import pickle
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
import lightgbm as lgb
import xgboost as xgb

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ml.training.data_loader import DataLoader
from ml.features.feature_manifest import get_model_a_features, validate_feature_columns
from ml.baseline.baseline_model import HistoricalRecoveryRateBaseline
from config.v1_config import get_config


def main():
    """Main training script for Prompt 7A."""
    print("=" * 70)
    print("RAY V1 - Prompt 7A: Model A Training + Baseline")
    print("=" * 70)
    print()

    config = get_config()
    seed = config.reproducibility.training_seed

    # Setup paths
    data_dir = project_root / "datasets" / "v1.0.0" / "ml"
    output_dir = project_root / "ml" / "models" / "v1.0.0"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize data loader
    print("[1/7] Loading data with test firewall...")
    loader = DataLoader(data_dir)

    # Load train and validation (NOT test)
    train_df = loader.load_train()
    val_df = loader.load_validation()

    print(f"  Train: {len(train_df)} rows, {len(train_df['customer_id'].unique())} customers")
    print(f"  Validation: {len(val_df)} rows, {len(val_df['customer_id'].unique())} customers")

    # Validate splits
    validation_result = loader.validate_splits()
    print(f"  Customer overlap: {validation_result['customer_overlap']} (should be 0)")
    print(f"  Test accessed: {validation_result['test_accessed']} (should be False)")

    assert validation_result['customer_overlap'] == 0, "Train/validation customer overlap detected!"
    assert not validation_result['test_accessed'], "Test set was accessed!"

    print("  ✓ Data firewall validated")
    print()

    # Validate features
    print("[2/7] Validating features...")
    validate_feature_columns(train_df.columns.tolist(), allow_target=True)
    validate_feature_columns(val_df.columns.tolist(), allow_target=True)
    print("  ✓ No forbidden features detected")
    print()

    # Train baseline
    print("[3/7] Training baseline (historical_recovery_rate)...")
    baseline = HistoricalRecoveryRateBaseline()
    baseline.fit(train_df, val_df)
    print()

    # Prepare Model A data
    print("[4/7] Preparing Model A data...")
    feature_cols = get_model_a_features()
    target_col = 'target'

    X_train = train_df[feature_cols]
    y_train = train_df[target_col]
    X_val = val_df[feature_cols]
    y_val = val_df[target_col]

    # Handle categorical features
    categorical_features = ['payment_method', 'failure_class']
    X_train_encoded = pd.get_dummies(X_train, columns=categorical_features, drop_first=True)
    X_val_encoded = pd.get_dummies(X_val, columns=categorical_features, drop_first=True)

    # Align validation columns with training
    missing_cols = set(X_train_encoded.columns) - set(X_val_encoded.columns)
    for col in missing_cols:
        X_val_encoded[col] = 0
    X_val_encoded = X_val_encoded[X_train_encoded.columns]

    print(f"  Features: {len(X_train_encoded.columns)}")
    print(f"  Train samples: {len(X_train_encoded)}")
    print(f"  Validation samples: {len(X_val_encoded)}")
    print()

    # Train Model A candidates
    print("[5/7] Training Model A candidates...")
    models = {}

    # Logistic Regression
    print("  Training Logistic Regression...")
    lr = LogisticRegression(random_state=seed, max_iter=1000, penalty='l2', C=1.0)
    lr.fit(X_train_encoded, y_train)
    y_pred_lr = lr.predict_proba(X_val_encoded)[:, 1]
    models['logistic_regression'] = {
        'model': lr,
        'features': X_train_encoded.columns.tolist(),
        'val_proba': y_pred_lr,
        'metrics': {
            'roc_auc': roc_auc_score(y_val, y_pred_lr),
            'pr_auc': average_precision_score(y_val, y_pred_lr),
            'brier_score': brier_score_loss(y_val, y_pred_lr),
        }
    }
    print(f"    ROC-AUC: {models['logistic_regression']['metrics']['roc_auc']:.4f}")
    print(f"    Brier: {models['logistic_regression']['metrics']['brier_score']:.4f}")

    # LightGBM
    print("  Training LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        random_state=seed,
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        num_leaves=31,
        verbose=-1
    )
    lgb_model.fit(X_train_encoded, y_train)
    y_pred_lgb = lgb_model.predict_proba(X_val_encoded)[:, 1]
    models['lightgbm'] = {
        'model': lgb_model,
        'features': X_train_encoded.columns.tolist(),
        'val_proba': y_pred_lgb,
        'metrics': {
            'roc_auc': roc_auc_score(y_val, y_pred_lgb),
            'pr_auc': average_precision_score(y_val, y_pred_lgb),
            'brier_score': brier_score_loss(y_val, y_pred_lgb),
        }
    }
    print(f"    ROC-AUC: {models['lightgbm']['metrics']['roc_auc']:.4f}")
    print(f"    Brier: {models['lightgbm']['metrics']['brier_score']:.4f}")

    # XGBoost
    print("  Training XGBoost...")
    xgb_model = xgb.XGBClassifier(
        random_state=seed,
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        eval_metric='logloss',
        verbosity=0
    )
    xgb_model.fit(X_train_encoded, y_train)
    y_pred_xgb = xgb_model.predict_proba(X_val_encoded)[:, 1]
    models['xgboost'] = {
        'model': xgb_model,
        'features': X_train_encoded.columns.tolist(),
        'val_proba': y_pred_xgb,
        'metrics': {
            'roc_auc': roc_auc_score(y_val, y_pred_xgb),
            'pr_auc': average_precision_score(y_val, y_pred_xgb),
            'brier_score': brier_score_loss(y_val, y_pred_xgb),
        }
    }
    print(f"    ROC-AUC: {models['xgboost']['metrics']['roc_auc']:.4f}")
    print(f"    Brier: {models['xgboost']['metrics']['brier_score']:.4f}")
    print()

    # Select best model (by Brier score)
    best_model_name = min(models.keys(), key=lambda k: models[k]['metrics']['brier_score'])
    print(f"[6/7] Selected Model A: {best_model_name}")
    print(f"  Validation ROC-AUC: {models[best_model_name]['metrics']['roc_auc']:.4f}")
    print(f"  Validation Brier: {models[best_model_name]['metrics']['brier_score']:.4f}")
    print()

    # Calibrate best model
    print("  Calibrating selected model...")
    calibrated = CalibratedClassifierCV(
        models[best_model_name]['model'],
        method='sigmoid',
        cv='prefit'
    )
    calibrated.fit(X_val_encoded, y_val)
    y_pred_calibrated = calibrated.predict_proba(X_val_encoded)[:, 1]

    calibrated_metrics = {
        'roc_auc': roc_auc_score(y_val, y_pred_calibrated),
        'pr_auc': average_precision_score(y_val, y_pred_calibrated),
        'brier_score': brier_score_loss(y_val, y_pred_calibrated),
    }
    print(f"  Calibrated Brier: {calibrated_metrics['brier_score']:.4f}")
    print()

    # Compare with baseline
    print("  Comparing with baseline...")
    baseline_proba = baseline.predict_proba(val_df)
    print(f"  Baseline ROC-AUC: {baseline.validation_metrics['roc_auc']:.4f}")
    print(f"  Baseline Brier: {baseline.validation_metrics['brier_score']:.4f}")
    print(f"  Model A ROC-AUC: {calibrated_metrics['roc_auc']:.4f}")
    print(f"  Model A Brier: {calibrated_metrics['brier_score']:.4f}")

    improvement = baseline.validation_metrics['roc_auc'] - calibrated_metrics['roc_auc']
    if improvement < 0:
        print(f"  ✓ Model A improves over baseline by {abs(improvement):.4f} ROC-AUC points")
    else:
        print(f"  ⚠ Model A does not improve over baseline ({improvement:.4f} worse)")
    print()

    # Save artifacts
    print("[7/7] Saving artifacts...")

    # Save Model A
    model_a_artifact = {
        'model': calibrated,
        'model_type': best_model_name,
        'features': models[best_model_name]['features'],
        'calibrated': True,
        'validation_metrics': calibrated_metrics,
    }
    model_a_path = output_dir / "model_a.pkl"
    with open(model_a_path, 'wb') as f:
        pickle.dump(model_a_artifact, f)
    print(f"  Saved Model A: {model_a_path}")

    # Save baseline
    baseline_path = output_dir / "baseline.pkl"
    with open(baseline_path, 'wb') as f:
        pickle.dump(baseline, f)
    print(f"  Saved baseline: {baseline_path}")

    # Save metadata
    metadata = {
        'prompt': '7A',
        'dataset_version': '1.0.0',
        'feature_manifest_version': '1.0.0',
        'random_seed': seed,
        'training_timestamp': datetime.now(timezone.utc).isoformat(),
        'train_rows': len(train_df),
        'train_customers': len(train_df['customer_id'].unique()),
        'validation_rows': len(val_df),
        'validation_customers': len(val_df['customer_id'].unique()),
        'test_accessed': False,
        'model_a': {
            'selected': best_model_name,
            'validation_metrics': calibrated_metrics,
        },
        'model_b': {
            'status': 'NOT_READY',
            'reason': 'Insufficient diagnosis coverage (100/700 opportunities)',
        },
        'baseline': {
            'type': 'HistoricalRecoveryRateBaseline',
            'validation_metrics': baseline.validation_metrics,
            'cold_start_fallback': baseline.cold_start_fallback,
            'threshold': baseline.threshold,
        }
    }

    metadata_path = output_dir / "training_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved metadata: {metadata_path}")
    print()

    # Final summary
    print("=" * 70)
    print("PROMPT 7A COMPLETE")
    print("=" * 70)
    print()
    print("Model A: READY")
    print(f"  Selected: {best_model_name}")
    print(f"  Calibrated: Yes")
    print(f"  Validation ROC-AUC: {calibrated_metrics['roc_auc']:.4f}")
    print()
    print("Baseline: READY")
    print(f"  Type: HistoricalRecoveryRateBaseline")
    print(f"  Validation ROC-AUC: {baseline.validation_metrics['roc_auc']:.4f}")
    print()
    print("Model B: NOT READY")
    print("  Reason: Insufficient diagnosis coverage")
    print("  Required: 550 TRAIN + 150 VALIDATION = 700 opportunities")
    print("  Available: 100 opportunities (14.3% coverage)")
    print("  Next step: Run full local Ollama diagnosis or skip Model B")
    print()
    print("Test Firewall: PASS")
    print("  Test set NOT accessed during training")
    print()
    print(f"Artifacts saved to: {output_dir}")
    print()


if __name__ == "__main__":
    main()
