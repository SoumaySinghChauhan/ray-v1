#!/usr/bin/env python
"""
RAY V1 - Prompt 7C: Train, Calibrate, Compare, and Freeze Models

Trains Model A (observable features) and Model B (observable + LLM diagnosis features).
Compares against frozen baseline.
Evaluates on VALIDATION only.
DOES NOT touch the 300-case TEST set.
"""

import sys
import json
import pickle
import warnings
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
)
import lightgbm as lgb
import xgboost as xgb

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ml.training.data_loader import DataLoader
from ml.features.feature_manifest import get_model_a_features, get_model_b_features, validate_feature_columns
from ml.baseline.baseline_model import HistoricalRecoveryRateBaseline
from config.v1_config import get_config

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=UserWarning)


class ModelTrainer:
    """Trains and evaluates Model A, Model B, and Baseline."""

    def __init__(self):
        """Initialize trainer."""
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "datasets" / "v1.0.0" / "ml"
        self.diagnosis_dir = self.project_root / "datasets" / "v1.0.0" / "diagnoses_local_v1"
        self.output_dir = self.project_root / "ml" / "models" / "v1.0.0"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.config = get_config()
        self.seed = self.config.reproducibility.training_seed

        # Test firewall tracking
        self.test_accessed = False

        # Results storage
        self.results = {
            'model_a': {},
            'model_b': {},
            'baseline': {},
            'comparison': {},
            'metadata': {},
        }

    def print_header(self, text: str):
        """Print section header."""
        print("\n" + "=" * 70)
        print(text)
        print("=" * 70)

    def load_and_validate_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load and validate training and validation data.

        Returns:
            (train_df, val_df)
        """
        self.print_header("STEP 1: LOAD AND VALIDATE DATA")

        # Load splits
        loader = DataLoader(self.data_dir)
        train_df = loader.load_train()
        val_df = loader.load_validation()

        print(f"Train: {len(train_df)} rows, {len(train_df['customer_id'].unique())} customers")
        print(f"Validation: {len(val_df)} rows, {len(val_df['customer_id'].unique())} customers")

        # Validate splits
        validation_result = loader.validate_splits()
        print(f"\nSplit validation:")
        print(f"  Train customers: {validation_result['train_customers']}")
        print(f"  Validation customers: {validation_result['validation_customers']}")
        print(f"  Customer overlap: {validation_result['customer_overlap']}")
        print(f"  Test accessed: {validation_result['test_accessed']}")

        # Assertions
        assert len(train_df) == 550, f"Expected 550 train rows, got {len(train_df)}"
        assert len(val_df) == 150, f"Expected 150 validation rows, got {len(val_df)}"
        assert validation_result['customer_overlap'] == 0, "Customer overlap detected!"
        assert not validation_result['test_accessed'], "Test set was accessed!"

        # Check for duplicates
        assert train_df['opportunity_id'].duplicated().sum() == 0, "Duplicate opportunity IDs in train!"
        assert val_df['opportunity_id'].duplicated().sum() == 0, "Duplicate opportunity IDs in validation!"

        # Validate features
        validate_feature_columns(train_df.columns.tolist(), allow_target=True, allow_identifiers=True)
        validate_feature_columns(val_df.columns.tolist(), allow_target=True, allow_identifiers=True)

        # Check target
        assert 'target' in train_df.columns, "Missing target column in train!"
        assert 'target' in val_df.columns, "Missing target column in validation!"
        assert train_df['target'].isin([0, 1]).all(), "Target must be binary!"
        assert val_df['target'].isin([0, 1]).all(), "Target must be binary!"

        print("\n✓ Data validation passed")

        self.test_accessed = validation_result['test_accessed']
        return train_df, val_df

    def load_diagnoses(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load and merge diagnosis features.

        Args:
            train_df: Training data
            val_df: Validation data

        Returns:
            (train_with_diagnosis, val_with_diagnosis)
        """
        self.print_header("STEP 2: LOAD DIAGNOSIS FEATURES")

        diagnosis_file = self.diagnosis_dir / "diagnoses.parquet"
        if not diagnosis_file.exists():
            print(f"WARNING: No diagnosis file found at {diagnosis_file}")
            print("Model B cannot be trained without diagnoses.")
            return None, None

        # Load diagnoses
        diagnoses = pd.read_parquet(diagnosis_file)
        print(f"Loaded {len(diagnoses)} diagnoses")
        print(f"Successful: {(diagnoses['diagnostic_status'] == 'success').sum()}")
        print(f"Failed: {(diagnoses['diagnostic_status'] != 'success').sum()}")

        # Merge with train
        train_with_dx = train_df.merge(
            diagnoses,
            on=['opportunity_id', 'customer_id'],
            how='left'
        )

        # Merge with validation
        val_with_dx = val_df.merge(
            diagnoses,
            on=['opportunity_id', 'customer_id'],
            how='left'
        )

        print(f"\nTrain with diagnosis: {len(train_with_dx)} rows")
        print(f"  Missing diagnosis: {train_with_dx['diagnostic_class'].isna().sum()}")
        print(f"\nValidation with diagnosis: {len(val_with_dx)} rows")
        print(f"  Missing diagnosis: {val_with_dx['diagnostic_class'].isna().sum()}")

        # Handle failed/missing diagnoses
        print("\nHandling failed/missing diagnoses:")
        print("  Strategy: Create indicator features for missing diagnosis")
        print("  - diagnosis_missing: 1 if diagnosis failed or missing, 0 otherwise")
        print("  - All diagnosis features set to 0/empty for missing cases")

        for df in [train_with_dx, val_with_dx]:
            df['diagnosis_missing'] = df['diagnostic_class'].isna().astype(int)
            df['diagnostic_class'] = df['diagnostic_class'].fillna('UNKNOWN')
            df['confidence'] = df['confidence'].fillna(0.0)

        print(f"\n✓ Diagnosis features loaded")
        print(f"  Train diagnosis_missing rate: {train_with_dx['diagnosis_missing'].mean():.1%}")
        print(f"  Validation diagnosis_missing rate: {val_with_dx['diagnosis_missing'].mean():.1%}")

        return train_with_dx, val_with_dx

    def train_baseline(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> HistoricalRecoveryRateBaseline:
        """
        Train frozen baseline model.

        Args:
            train_df: Training data
            val_df: Validation data

        Returns:
            Trained baseline model
        """
        self.print_header("STEP 3: TRAIN BASELINE")

        baseline = HistoricalRecoveryRateBaseline()
        metrics = baseline.fit(train_df, val_df)

        self.results['baseline'] = {
            'model': baseline,
            'validation_metrics': metrics,
            'cold_start_fallback': baseline.cold_start_fallback,
            'threshold': baseline.threshold,
        }

        print("\n✓ Baseline trained")
        return baseline

    def prepare_model_a_data(self, train_df: pd.DataFrame, val_df: pd.DataFrame):
        """
        Prepare Model A training data (observable features only).

        Returns:
            (X_train, y_train, X_val, y_val, feature_names)
        """
        self.print_header("STEP 4: PREPARE MODEL A DATA")

        feature_cols = get_model_a_features()
        target_col = 'target'

        X_train = train_df[feature_cols].copy()
        y_train = train_df[target_col].copy()
        X_val = val_df[feature_cols].copy()
        y_val = val_df[target_col].copy()

        # Handle categorical features
        categorical_features = ['payment_method', 'failure_class']
        X_train_encoded = pd.get_dummies(X_train, columns=categorical_features, drop_first=True)
        X_val_encoded = pd.get_dummies(X_val, columns=categorical_features, drop_first=True)

        # Align validation columns with training
        missing_cols = set(X_train_encoded.columns) - set(X_val_encoded.columns)
        for col in missing_cols:
            X_val_encoded[col] = 0
        X_val_encoded = X_val_encoded[X_train_encoded.columns]

        print(f"Features: {len(X_train_encoded.columns)}")
        print(f"Train samples: {len(X_train_encoded)}")
        print(f"Validation samples: {len(X_val_encoded)}")
        print(f"Target distribution (train): {y_train.value_counts().to_dict()}")
        print(f"Target distribution (val): {y_val.value_counts().to_dict()}")

        return X_train_encoded, y_train, X_val_encoded, y_val, X_train_encoded.columns.tolist()

    def train_model_a(self, X_train, y_train, X_val, y_val, feature_names):
        """
        Train Model A candidates and select best.

        Returns:
            dict with best model info
        """
        self.print_header("STEP 5: TRAIN MODEL A CANDIDATES")

        models = {}

        # Logistic Regression
        print("\n[Model A.1] Logistic Regression...")
        lr = LogisticRegression(random_state=self.seed, max_iter=1000, penalty='l2', C=1.0)
        lr.fit(X_train, y_train)
        y_pred_lr = lr.predict_proba(X_val)[:, 1]

        models['logistic_regression'] = {
            'model': lr,
            'features': feature_names,
            'val_proba': y_pred_lr,
            'metrics': {
                'roc_auc': roc_auc_score(y_val, y_pred_lr),
                'pr_auc': average_precision_score(y_val, y_pred_lr),
                'brier_score': brier_score_loss(y_val, y_pred_lr),
                'log_loss': log_loss(y_val, y_pred_lr),
            }
        }
        print(f"  ROC-AUC: {models['logistic_regression']['metrics']['roc_auc']:.4f}")
        print(f"  Brier: {models['logistic_regression']['metrics']['brier_score']:.4f}")

        # LightGBM
        print("\n[Model A.2] LightGBM...")
        lgb_model = lgb.LGBMClassifier(
            random_state=self.seed,
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            num_leaves=31,
            verbose=-1
        )
        lgb_model.fit(X_train, y_train)
        y_pred_lgb = lgb_model.predict_proba(X_val)[:, 1]

        models['lightgbm'] = {
            'model': lgb_model,
            'features': feature_names,
            'val_proba': y_pred_lgb,
            'metrics': {
                'roc_auc': roc_auc_score(y_val, y_pred_lgb),
                'pr_auc': average_precision_score(y_val, y_pred_lgb),
                'brier_score': brier_score_loss(y_val, y_pred_lgb),
                'log_loss': log_loss(y_val, y_pred_lgb),
            }
        }
        print(f"  ROC-AUC: {models['lightgbm']['metrics']['roc_auc']:.4f}")
        print(f"  Brier: {models['lightgbm']['metrics']['brier_score']:.4f}")

        # XGBoost
        print("\n[Model A.3] XGBoost...")
        xgb_model = xgb.XGBClassifier(
            random_state=self.seed,
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            eval_metric='logloss',
            verbosity=0
        )
        xgb_model.fit(X_train, y_train)
        y_pred_xgb = xgb_model.predict_proba(X_val)[:, 1]

        models['xgboost'] = {
            'model': xgb_model,
            'features': feature_names,
            'val_proba': y_pred_xgb,
            'metrics': {
                'roc_auc': roc_auc_score(y_val, y_pred_xgb),
                'pr_auc': average_precision_score(y_val, y_pred_xgb),
                'brier_score': brier_score_loss(y_val, y_pred_xgb),
                'log_loss': log_loss(y_val, y_pred_xgb),
            }
        }
        print(f"  ROC-AUC: {models['xgboost']['metrics']['roc_auc']:.4f}")
        print(f"  Brier: {models['xgboost']['metrics']['brier_score']:.4f}")

        # Select best by Brier score (probability quality)
        best_model_name = min(models.keys(), key=lambda k: models[k]['metrics']['brier_score'])
        best_model_info = models[best_model_name]

        print(f"\n✓ Selected Model A: {best_model_name}")
        print(f"  Validation ROC-AUC: {best_model_info['metrics']['roc_auc']:.4f}")
        print(f"  Validation Brier: {best_model_info['metrics']['brier_score']:.4f}")

        # Calibrate best model
        print(f"\n[Calibration] Calibrating {best_model_name}...")
        # Note: We calibrate on training set and evaluate on validation
        # Using Platt scaling (sigmoid)
        calibrated = CalibratedClassifierCV(
            best_model_info['model'],
            method='sigmoid',
            cv=3  # 3-fold cross-validation for calibration
        )
        # Fit calibration on training data
        calibrated.fit(X_train, y_train)
        y_pred_calibrated = calibrated.predict_proba(X_val)[:, 1]

        calibrated_metrics = {
            'roc_auc': roc_auc_score(y_val, y_pred_calibrated),
            'pr_auc': average_precision_score(y_val, y_pred_calibrated),
            'brier_score': brier_score_loss(y_val, y_pred_calibrated),
            'log_loss': log_loss(y_val, y_pred_calibrated),
        }
        print(f"  Calibrated Brier: {calibrated_metrics['brier_score']:.4f}")
        print(f"  Calibrated ROC-AUC: {calibrated_metrics['roc_auc']:.4f}")

        self.results['model_a'] = {
            'selected': best_model_name,
            'uncalibrated_model': best_model_info['model'],
            'calibrated_model': calibrated,
            'features': best_model_info['features'],
            'uncalibrated_metrics': best_model_info['metrics'],
            'calibrated_metrics': calibrated_metrics,
            'all_candidates': {k: v['metrics'] for k, v in models.items()},
        }

        return self.results['model_a']

    def prepare_model_b_data(self, train_df: pd.DataFrame, val_df: pd.DataFrame):
        """
        Prepare Model B training data (observable + diagnosis features).

        Returns:
            (X_train, y_train, X_val, y_val, feature_names) or (None, None, None, None, None) if not possible
        """
        self.print_header("STEP 6: PREPARE MODEL B DATA")

        if train_df is None or val_df is None:
            print("ERROR: Cannot prepare Model B data - diagnosis features not available")
            return None, None, None, None, None

        # Get base features
        base_features = get_model_a_features()

        # Add diagnosis features
        diagnosis_features = [
            'diagnostic_class',
            'confidence',
            'diagnosis_missing',
        ]

        # Check that diagnosis features exist
        for feat in diagnosis_features:
            if feat not in train_df.columns:
                print(f"ERROR: Missing diagnosis feature: {feat}")
                return None, None, None, None, None

        all_features = base_features + diagnosis_features
        target_col = 'target'

        X_train = train_df[all_features].copy()
        y_train = train_df[target_col].copy()
        X_val = val_df[all_features].copy()
        y_val = val_df[target_col].copy()

        # Handle categorical features
        categorical_features = ['payment_method', 'failure_class', 'diagnostic_class']
        X_train_encoded = pd.get_dummies(X_train, columns=categorical_features, drop_first=True)
        X_val_encoded = pd.get_dummies(X_val, columns=categorical_features, drop_first=True)

        # Align validation columns with training
        missing_cols = set(X_train_encoded.columns) - set(X_val_encoded.columns)
        for col in missing_cols:
            X_val_encoded[col] = 0
        X_val_encoded = X_val_encoded[X_train_encoded.columns]

        print(f"Features: {len(X_train_encoded.columns)}")
        print(f"  Base features: {len(base_features)}")
        print(f"  Diagnosis features: {len(diagnosis_features)}")
        print(f"  After encoding: {len(X_train_encoded.columns)}")
        print(f"Train samples: {len(X_train_encoded)}")
        print(f"Validation samples: {len(X_val_encoded)}")

        return X_train_encoded, y_train, X_val_encoded, y_val, X_train_encoded.columns.tolist()

    def train_model_b(self, X_train, y_train, X_val, y_val, feature_names):
        """
        Train Model B candidates and select best.

        Returns:
            dict with best model info, or None if training not possible
        """
        self.print_header("STEP 7: TRAIN MODEL B CANDIDATES")

        if X_train is None:
            print("SKIPPED: Model B cannot be trained without diagnosis features")
            self.results['model_b'] = {
                'status': 'NOT_TRAINED',
                'reason': 'Diagnosis features not available',
            }
            return None

        models = {}

        # Logistic Regression
        print("\n[Model B.1] Logistic Regression...")
        lr = LogisticRegression(random_state=self.seed, max_iter=1000, penalty='l2', C=1.0)
        lr.fit(X_train, y_train)
        y_pred_lr = lr.predict_proba(X_val)[:, 1]

        models['logistic_regression'] = {
            'model': lr,
            'features': feature_names,
            'val_proba': y_pred_lr,
            'metrics': {
                'roc_auc': roc_auc_score(y_val, y_pred_lr),
                'pr_auc': average_precision_score(y_val, y_pred_lr),
                'brier_score': brier_score_loss(y_val, y_pred_lr),
                'log_loss': log_loss(y_val, y_pred_lr),
            }
        }
        print(f"  ROC-AUC: {models['logistic_regression']['metrics']['roc_auc']:.4f}")
        print(f"  Brier: {models['logistic_regression']['metrics']['brier_score']:.4f}")

        # LightGBM
        print("\n[Model B.2] LightGBM...")
        lgb_model = lgb.LGBMClassifier(
            random_state=self.seed,
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            num_leaves=31,
            verbose=-1
        )
        lgb_model.fit(X_train, y_train)
        y_pred_lgb = lgb_model.predict_proba(X_val)[:, 1]

        models['lightgbm'] = {
            'model': lgb_model,
            'features': feature_names,
            'val_proba': y_pred_lgb,
            'metrics': {
                'roc_auc': roc_auc_score(y_val, y_pred_lgb),
                'pr_auc': average_precision_score(y_val, y_pred_lgb),
                'brier_score': brier_score_loss(y_val, y_pred_lgb),
                'log_loss': log_loss(y_val, y_pred_lgb),
            }
        }
        print(f"  ROC-AUC: {models['lightgbm']['metrics']['roc_auc']:.4f}")
        print(f"  Brier: {models['lightgbm']['metrics']['brier_score']:.4f}")

        # XGBoost
        print("\n[Model B.3] XGBoost...")
        xgb_model = xgb.XGBClassifier(
            random_state=self.seed,
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            eval_metric='logloss',
            verbosity=0
        )
        xgb_model.fit(X_train, y_train)
        y_pred_xgb = xgb_model.predict_proba(X_val)[:, 1]

        models['xgboost'] = {
            'model': xgb_model,
            'features': feature_names,
            'val_proba': y_pred_xgb,
            'metrics': {
                'roc_auc': roc_auc_score(y_val, y_pred_xgb),
                'pr_auc': average_precision_score(y_val, y_pred_xgb),
                'brier_score': brier_score_loss(y_val, y_pred_xgb),
                'log_loss': log_loss(y_val, y_pred_xgb),
            }
        }
        print(f"  ROC-AUC: {models['xgboost']['metrics']['roc_auc']:.4f}")
        print(f"  Brier: {models['xgboost']['metrics']['brier_score']:.4f}")

        # Select best by Brier score
        best_model_name = min(models.keys(), key=lambda k: models[k]['metrics']['brier_score'])
        best_model_info = models[best_model_name]

        print(f"\n✓ Selected Model B: {best_model_name}")
        print(f"  Validation ROC-AUC: {best_model_info['metrics']['roc_auc']:.4f}")
        print(f"  Validation Brier: {best_model_info['metrics']['brier_score']:.4f}")

        # Calibrate best model
        print(f"\n[Calibration] Calibrating {best_model_name}...")
        # Note: We calibrate on training set and evaluate on validation
        # Using Platt scaling (sigmoid)
        calibrated = CalibratedClassifierCV(
            best_model_info['model'],
            method='sigmoid',
            cv=3  # 3-fold cross-validation for calibration
        )
        # Fit calibration on training data
        calibrated.fit(X_train, y_train)
        y_pred_calibrated = calibrated.predict_proba(X_val)[:, 1]

        calibrated_metrics = {
            'roc_auc': roc_auc_score(y_val, y_pred_calibrated),
            'pr_auc': average_precision_score(y_val, y_pred_calibrated),
            'brier_score': brier_score_loss(y_val, y_pred_calibrated),
            'log_loss': log_loss(y_val, y_pred_calibrated),
        }
        print(f"  Calibrated Brier: {calibrated_metrics['brier_score']:.4f}")
        print(f"  Calibrated ROC-AUC: {calibrated_metrics['roc_auc']:.4f}")

        self.results['model_b'] = {
            'status': 'TRAINED',
            'selected': best_model_name,
            'uncalibrated_model': best_model_info['model'],
            'calibrated_model': calibrated,
            'features': best_model_info['features'],
            'uncalibrated_metrics': best_model_info['metrics'],
            'calibrated_metrics': calibrated_metrics,
            'all_candidates': {k: v['metrics'] for k, v in models.items()},
        }

        return self.results['model_b']

    def compare_models(self):
        """Generate comparison table."""
        self.print_header("STEP 8: MODEL COMPARISON (VALIDATION)")

        # Build comparison table
        comparison = []

        # Baseline
        baseline_metrics = self.results['baseline']['validation_metrics']
        comparison.append({
            'Model': 'Baseline',
            'ROC-AUC': f"{baseline_metrics['roc_auc']:.4f}",
            'PR-AUC': f"{baseline_metrics['pr_auc']:.4f}",
            'Brier': f"{baseline_metrics['brier_score']:.4f}",
            'Log Loss': 'N/A',
        })

        # Model A (calibrated)
        model_a_metrics = self.results['model_a']['calibrated_metrics']
        comparison.append({
            'Model': f"Model A ({self.results['model_a']['selected']}, calibrated)",
            'ROC-AUC': f"{model_a_metrics['roc_auc']:.4f}",
            'PR-AUC': f"{model_a_metrics['pr_auc']:.4f}",
            'Brier': f"{model_a_metrics['brier_score']:.4f}",
            'Log Loss': f"{model_a_metrics['log_loss']:.4f}",
        })

        # Model B (calibrated) if trained
        if self.results['model_b'].get('status') == 'TRAINED':
            model_b_metrics = self.results['model_b']['calibrated_metrics']
            comparison.append({
                'Model': f"Model B ({self.results['model_b']['selected']}, calibrated)",
                'ROC-AUC': f"{model_b_metrics['roc_auc']:.4f}",
                'PR-AUC': f"{model_b_metrics['pr_auc']:.4f}",
                'Brier': f"{model_b_metrics['brier_score']:.4f}",
                'Log Loss': f"{model_b_metrics['log_loss']:.4f}",
            })
        else:
            comparison.append({
                'Model': 'Model B',
                'ROC-AUC': 'NOT TRAINED',
                'PR-AUC': 'NOT TRAINED',
                'Brier': 'NOT TRAINED',
                'Log Loss': 'NOT TRAINED',
            })

        # Print comparison
        df_comparison = pd.DataFrame(comparison)
        print("\nValidation Metrics Comparison:")
        print(df_comparison.to_string(index=False))

        # LLM Contribution Analysis
        print("\n\nLLM Diagnosis Contribution:")
        if self.results['model_b'].get('status') == 'TRAINED':
            model_a_auc = self.results['model_a']['calibrated_metrics']['roc_auc']
            model_b_auc = self.results['model_b']['calibrated_metrics']['roc_auc']
            model_a_brier = self.results['model_a']['calibrated_metrics']['brier_score']
            model_b_brier = self.results['model_b']['calibrated_metrics']['brier_score']

            auc_improvement = model_b_auc - model_a_auc
            brier_improvement = model_a_brier - model_b_brier  # Lower is better

            print(f"  ROC-AUC change (Model B - Model A): {auc_improvement:+.4f}")
            print(f"  Brier change (Model A - Model B): {brier_improvement:+.4f}")

            if auc_improvement > 0.01 and brier_improvement > 0:
                conclusion = "LLM diagnosis adds MEASURABLE VALUE"
            elif auc_improvement > 0 or brier_improvement > 0:
                conclusion = "LLM diagnosis adds MARGINAL VALUE"
            else:
                conclusion = "NO MEASURABLE VALUE from LLM diagnosis"

            print(f"\n  Conclusion: {conclusion}")
        else:
            print("  CANNOT ASSESS - Model B not trained")

        self.results['comparison'] = df_comparison.to_dict('records')

    def save_artifacts(self):
        """Save model artifacts."""
        self.print_header("STEP 9: SAVE ARTIFACTS")

        # Save Model A
        model_a_path = self.output_dir / "model_a_calibrated.pkl"
        with open(model_a_path, 'wb') as f:
            pickle.dump({
                'model': self.results['model_a']['calibrated_model'],
                'model_type': self.results['model_a']['selected'],
                'features': self.results['model_a']['features'],
                'calibrated': True,
                'validation_metrics': self.results['model_a']['calibrated_metrics'],
            }, f)
        print(f"Saved: {model_a_path}")

        # Save baseline
        baseline_path = self.output_dir / "baseline.pkl"
        with open(baseline_path, 'wb') as f:
            pickle.dump(self.results['baseline']['model'], f)
        print(f"Saved: {baseline_path}")

        # Save Model B if trained
        if self.results['model_b'].get('status') == 'TRAINED':
            model_b_path = self.output_dir / "model_b_calibrated.pkl"
            with open(model_b_path, 'wb') as f:
                pickle.dump({
                    'model': self.results['model_b']['calibrated_model'],
                    'model_type': self.results['model_b']['selected'],
                    'features': self.results['model_b']['features'],
                    'calibrated': True,
                    'validation_metrics': self.results['model_b']['calibrated_metrics'],
                }, f)
            print(f"Saved: {model_b_path}")

        # Save metadata
        import sklearn
        metadata = {
            'prompt': '7C',
            'dataset_version': '1.0.0',
            'diagnosis_version': '1.0.0',
            'feature_manifest_version': '1.0.0',
            'random_seed': self.seed,
            'training_timestamp': datetime.now(timezone.utc).isoformat(),
            'test_accessed': self.test_accessed,
            'python_version': sys.version,
            'sklearn_version': sklearn.__version__,
            'lightgbm_version': lgb.__version__,
            'xgboost_version': xgb.__version__,
            'model_a': {
                'selected': self.results['model_a']['selected'],
                'calibrated': True,
                'validation_metrics': self.results['model_a']['calibrated_metrics'],
            },
            'model_b': {
                'status': self.results['model_b'].get('status', 'NOT_TRAINED'),
                'selected': self.results['model_b'].get('selected'),
                'calibrated': self.results['model_b'].get('status') == 'TRAINED',
                'validation_metrics': self.results['model_b'].get('calibrated_metrics'),
            },
            'baseline': {
                'type': 'HistoricalRecoveryRateBaseline',
                'validation_metrics': self.results['baseline']['validation_metrics'],
            },
            'comparison': self.results['comparison'],
        }

        metadata_path = self.output_dir / "training_metadata_7c.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Saved: {metadata_path}")

        print(f"\n✓ All artifacts saved to: {self.output_dir}")

    def run(self):
        """Main training flow."""
        self.print_header("RAY V1 - PROMPT 7C: TRAIN AND COMPARE MODELS")

        # Load data
        train_df, val_df = self.load_and_validate_data()

        # Load diagnoses
        train_with_dx, val_with_dx = self.load_diagnoses(train_df, val_df)

        # Train baseline
        baseline = self.train_baseline(train_df, val_df)

        # Train Model A
        X_train_a, y_train_a, X_val_a, y_val_a, features_a = self.prepare_model_a_data(train_df, val_df)
        model_a = self.train_model_a(X_train_a, y_train_a, X_val_a, y_val_a, features_a)

        # Train Model B
        X_train_b, y_train_b, X_val_b, y_val_b, features_b = self.prepare_model_b_data(train_with_dx, val_with_dx)
        model_b = self.train_model_b(X_train_b, y_train_b, X_val_b, y_val_b, features_b)

        # Compare
        self.compare_models()

        # Save artifacts
        self.save_artifacts()

        # Final test firewall check
        self.print_header("STEP 10: FINAL TEST FIREWALL CHECK")
        print(f"Test accessed: {self.test_accessed}")
        if not self.test_accessed:
            print("✓ TEST FIREWALL MAINTAINED - Zero test set access")
        else:
            raise RuntimeError("CRITICAL: Test set was accessed!")

        self.print_header("PROMPT 7C COMPLETE")
        print("\n✓ Models trained and calibrated")
        print("✓ Baseline compared")
        print("✓ Artifacts saved")
        print("✓ Test firewall maintained")
        print(f"\nArtifacts: {self.output_dir}")


def main():
    """Main entry point."""
    trainer = ModelTrainer()
    trainer.run()


if __name__ == "__main__":
    main()
