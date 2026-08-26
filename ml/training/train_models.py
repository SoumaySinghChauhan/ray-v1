"""
ML model training for RAY V1 recovery prediction.

Trains Model A (observable features) and Model B (observable + LLM diagnosis).
"""

import json
import pickle
import warnings
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_curve,
    precision_recall_curve
)
import lightgbm as lgb
import xgboost as xgb

from ml.training.data_loader import DataLoader, load_diagnosis_data
from ml.features.feature_manifest import (
    get_model_a_features,
    get_model_b_features,
    validate_feature_columns
)
from config.v1_config import get_config


class ModelTrainer:
    """Trains and evaluates recovery prediction models."""

    def __init__(self, data_dir: Path, diagnosis_path: Path, output_dir: Path):
        """
        Initialize model trainer.

        Args:
            data_dir: Directory with train/validation/test parquet files
            diagnosis_path: Path to local Ollama diagnosis file
            output_dir: Directory to save model artifacts
        """
        self.data_dir = Path(data_dir)
        self.diagnosis_path = Path(diagnosis_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.config = get_config()
        self.loader = DataLoader(data_dir)

        # Model metadata
        self.training_metadata = {
            'dataset_version': '1.0.0',
            'diagnosis_version': '1.1.0-pilot',
            'random_seed': self.config.reproducibility.training_seed,
            'training_timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def prepare_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Load and prepare training/validation data with diagnosis features.

        Returns:
            (train_df, validation_df, diagnosis_df)
        """
        print("[1/7] Loading data...")

        # Load train and validation
        train_df = self.loader.load_train()
        val_df = self.loader.load_validation()

        print(f"  Train: {len(train_df)} rows, {len(train_df['customer_id'].unique())} customers")
        print(f"  Validation: {len(val_df)} rows, {len(val_df['customer_id'].unique())} customers")

        # Load diagnosis data
        diagnosis_df = load_diagnosis_data(self.diagnosis_path)
        print(f"  Diagnosis: {len(diagnosis_df)} rows")
        print(f"    Successful: {diagnosis_df['diagnostic_class'].notna().sum()}")
        print(f"    Failed: {diagnosis_df['diagnostic_class'].isna().sum()}")

        # Validate no test set access
        validation_result = self.loader.validate_splits()
        assert not validation_result['test_accessed'], "Test set was accessed!"

        # Validate features
        validate_feature_columns(train_df.columns.tolist(), allow_target=True)
        validate_feature_columns(val_df.columns.tolist(), allow_target=True)

        return train_df, val_df, diagnosis_df

    def train_model_a(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Train Model A (observable features only).

        Args:
            train_df: Training data
            val_df: Validation data

        Returns:
            Dictionary with trained models and metrics
        """
        print("\n[2/7] Training Model A (observable features only)...")

        feature_cols = get_model_a_features()
        target_col = 'payment_link_recovered'

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

        models = {}
        seed = self.config.reproducibility.training_seed

        # Logistic Regression
        print("  Training Logistic Regression...")
        lr = LogisticRegression(random_state=seed, max_iter=1000, penalty='l2', C=1.0)
        lr.fit(X_train_encoded, y_train)
        models['logistic_regression'] = {
            'model': lr,
            'features': X_train_encoded.columns.tolist(),
            'calibrated': False
        }

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
        models['lightgbm'] = {
            'model': lgb_model,
            'features': X_train_encoded.columns.tolist(),
            'calibrated': False
        }

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
        models['xgboost'] = {
            'model': xgb_model,
            'features': X_train_encoded.columns.tolist(),
            'calibrated': False
        }

        # Evaluate all models
        print("  Evaluating models on validation set...")
        for name, model_dict in models.items():
            model = model_dict['model']
            y_pred_proba = model.predict_proba(X_val_encoded)[:, 1]

            metrics = self._compute_metrics(y_val, y_pred_proba)
            model_dict['validation_metrics'] = metrics

            print(f"    {name}:")
            print(f"      ROC-AUC: {metrics['roc_auc']:.4f}")
            print(f"      PR-AUC: {metrics['pr_auc']:.4f}")
            print(f"      Brier: {metrics['brier_score']:.4f}")

        return models

    def train_model_b(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        diagnosis_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Train Model B (observable + LLM diagnosis features).

        Args:
            train_df: Training data
            val_df: Validation data
            diagnosis_df: Diagnosis features

        Returns:
            Dictionary with trained models and metrics
        """
        print("\n[3/7] Training Model B (observable + LLM diagnosis)...")

        # Merge diagnosis features
        train_with_diag = self._merge_diagnosis_features(train_df, diagnosis_df)
        val_with_diag = self._merge_diagnosis_features(val_df, diagnosis_df)

        print(f"  Train with diagnosis: {len(train_with_diag)} rows " +
              f"({len(train_with_diag[train_with_diag['diagnostic_class'].notna()])} with valid diagnosis)")
        print(f"  Validation with diagnosis: {len(val_with_diag)} rows " +
              f"({len(val_with_diag[val_with_diag['diagnostic_class'].notna()])} with valid diagnosis)")

        feature_cols = get_model_b_features()
        target_col = 'payment_link_recovered'

        # Filter to rows with valid diagnosis
        train_with_diag = train_with_diag[train_with_diag['diagnostic_class'].notna()].copy()
        val_with_diag = val_with_diag[val_with_diag['diagnostic_class'].notna()].copy()

        if len(train_with_diag) == 0:
            print("  WARNING: No training rows with valid diagnosis. Skipping Model B.")
            return {}

        X_train = train_with_diag[feature_cols]
        y_train = train_with_diag[target_col]
        X_val = val_with_diag[feature_cols]
        y_val = val_with_diag[target_col]

        # Handle categorical features
        categorical_features = ['payment_method', 'failure_class', 'diagnostic_class']
        X_train_encoded = pd.get_dummies(X_train, columns=categorical_features, drop_first=True)
        X_val_encoded = pd.get_dummies(X_val, columns=categorical_features, drop_first=True)

        # Align columns
        missing_cols = set(X_train_encoded.columns) - set(X_val_encoded.columns)
        for col in missing_cols:
            X_val_encoded[col] = 0
        X_val_encoded = X_val_encoded[X_train_encoded.columns]

        models = {}
        seed = self.config.reproducibility.training_seed

        # Logistic Regression
        print("  Training Logistic Regression...")
        lr = LogisticRegression(random_state=seed, max_iter=1000, penalty='l2', C=1.0)
        lr.fit(X_train_encoded, y_train)
        models['logistic_regression'] = {
            'model': lr,
            'features': X_train_encoded.columns.tolist(),
            'calibrated': False
        }

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
        models['lightgbm'] = {
            'model': lgb_model,
            'features': X_train_encoded.columns.tolist(),
            'calibrated': False
        }

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
        models['xgboost'] = {
            'model': xgb_model,
            'features': X_train_encoded.columns.tolist(),
            'calibrated': False
        }

        # Evaluate
        print("  Evaluating models on validation set...")
        for name, model_dict in models.items():
            model = model_dict['model']
            y_pred_proba = model.predict_proba(X_val_encoded)[:, 1]

            metrics = self._compute_metrics(y_val, y_pred_proba)
            model_dict['validation_metrics'] = metrics

            print(f"    {name}:")
            print(f"      ROC-AUC: {metrics['roc_auc']:.4f}")
            print(f"      PR-AUC: {metrics['pr_auc']:.4f}")
            print(f"      Brier: {metrics['brier_score']:.4f}")

        return models

    def _merge_diagnosis_features(
        self,
        df: pd.DataFrame,
        diagnosis_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Merge diagnosis features into main DataFrame."""
        # Select diagnosis columns
        diag_cols = ['opportunity_id', 'diagnostic_class', 'confidence']
        diag_features = diagnosis_df[diag_cols].copy()

        # Merge
        merged = df.merge(diag_features, on='opportunity_id', how='left', suffixes=('', '_diag'))

        # Rename confidence to diagnostic_confidence
        if 'confidence' in merged.columns:
            merged['diagnostic_confidence'] = merged['confidence']
            merged = merged.drop(columns=['confidence'])

        # Add reason code features (all False for pilot - not extracted yet)
        merged['reason_code_temporary_failure'] = False
        merged['reason_code_persistent_failure'] = False
        merged['reason_code_strong_payment_history'] = False
        merged['reason_code_high_recovery_history'] = False

        return merged

    def _compute_metrics(self, y_true: np.ndarray, y_pred_proba: np.ndarray) -> Dict[str, float]:
        """Compute validation metrics."""
        return {
            'roc_auc': roc_auc_score(y_true, y_pred_proba),
            'pr_auc': average_precision_score(y_true, y_pred_proba),
            'brier_score': brier_score_loss(y_true, y_pred_proba),
            'log_loss': log_loss(y_true, y_pred_proba),
        }

    def calibrate_models(
        self,
        models_dict: Dict[str, Any],
        X_val: pd.DataFrame,
        y_val: np.ndarray
    ) -> Dict[str, Any]:
        """
        Calibrate models using validation set.

        Args:
            models_dict: Dictionary of trained models
            X_val: Validation features
            y_val: Validation labels

        Returns:
            Dictionary with calibrated models
        """
        print("\n[4/7] Calibrating models...")

        calibrated_models = {}

        for name, model_dict in models_dict.items():
            print(f"  Calibrating {name}...")

            model = model_dict['model']

            # Calibrate with sigmoid (Platt scaling)
            calibrated = CalibratedClassifierCV(
                model,
                method='sigmoid',
                cv='prefit'
            )

            # Fit on validation set
            calibrated.fit(X_val, y_val)

            calibrated_models[name] = {
                'model': calibrated,
                'features': model_dict['features'],
                'calibrated': True,
                'validation_metrics_uncalibrated': model_dict['validation_metrics']
            }

            # Evaluate calibrated model
            y_pred_proba_cal = calibrated.predict_proba(X_val)[:, 1]
            metrics_cal = self._compute_metrics(y_val, y_pred_proba_cal)
            calibrated_models[name]['validation_metrics_calibrated'] = metrics_cal

            print(f"    Uncalibrated Brier: {model_dict['validation_metrics']['brier_score']:.4f}")
            print(f"    Calibrated Brier: {metrics_cal['brier_score']:.4f}")

        return calibrated_models

    def save_artifacts(
        self,
        model_a_models: Dict[str, Any],
        model_b_models: Dict[str, Any],
        selected_model_a: str,
        selected_model_b: str
    ):
        """Save model artifacts to disk."""
        print("\n[7/7] Saving model artifacts...")

        artifacts_dir = self.output_dir / "v1.0.0"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Save selected Model A
        if selected_model_a in model_a_models:
            model_a_path = artifacts_dir / "model_a.pkl"
            with open(model_a_path, 'wb') as f:
                pickle.dump(model_a_models[selected_model_a], f)
            print(f"  Saved Model A: {model_a_path}")

        # Save selected Model B
        if selected_model_b and selected_model_b in model_b_models:
            model_b_path = artifacts_dir / "model_b.pkl"
            with open(model_b_path, 'wb') as f:
                pickle.dump(model_b_models[selected_model_b], f)
            print(f"  Saved Model B: {model_b_path}")

        # Save metadata
        metadata = {
            **self.training_metadata,
            'selected_model_a': selected_model_a,
            'selected_model_b': selected_model_b,
            'model_a_validation_metrics': model_a_models[selected_model_a]['validation_metrics_calibrated'],
            'model_b_validation_metrics': model_b_models[selected_model_b]['validation_metrics_calibrated'] if selected_model_b in model_b_models else None,
        }

        metadata_path = artifacts_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  Saved metadata: {metadata_path}")

        print("\n✓ Training complete!")
        print(f"  Artifacts saved to: {artifacts_dir}")


def main():
    """Main training entry point."""
    from pathlib import Path

    # Paths
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "datasets" / "v1.0.0" / "ml"
    diagnosis_path = project_root / "datasets" / "v1.0.0" / "diagnoses_local" / "diagnoses_pilot_100.parquet"
    output_dir = project_root / "ml" / "models"

    # Initialize trainer
    trainer = ModelTrainer(data_dir, diagnosis_path, output_dir)

    # Prepare data
    train_df, val_df, diagnosis_df = trainer.prepare_data()

    # Train Model A
    model_a_models = trainer.train_model_a(train_df, val_df)

    # Train Model B
    model_b_models = trainer.train_model_b(train_df, val_df, diagnosis_df)

    # Select best models (simple selection by Brier score)
    best_model_a = min(
        model_a_models.keys(),
        key=lambda k: model_a_models[k]['validation_metrics']['brier_score']
    )
    print(f"\n[5/7] Selected Model A: {best_model_a}")

    if model_b_models:
        best_model_b = min(
            model_b_models.keys(),
            key=lambda k: model_b_models[k]['validation_metrics']['brier_score']
        )
        print(f"[6/7] Selected Model B: {best_model_b}")
    else:
        best_model_b = None
        print("[6/7] Model B training skipped (no diagnosis data)")

    # Save artifacts
    trainer.save_artifacts(model_a_models, model_b_models, best_model_a, best_model_b or '')


if __name__ == "__main__":
    main()
