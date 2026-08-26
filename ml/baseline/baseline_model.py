"""
Baseline model using customer historical recovery rate.

This is the frozen baseline from earlier validation work.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss


class HistoricalRecoveryRateBaseline:
    """
    Baseline predictor using customer_historical_recovery_rate.

    Frozen configuration from validation:
    - Threshold: validation-derived (to be loaded)
    - Cold-start fallback: validation-derived mean (to be loaded)
    """

    def __init__(self, cold_start_fallback: float = None):
        """
        Initialize baseline model.

        Args:
            cold_start_fallback: Fallback recovery rate for customers with no history.
                                If None, will be computed from validation set.
        """
        self.cold_start_fallback = cold_start_fallback
        self.threshold = None  # Set after validation
        self.validation_metrics = {}

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict recovery probability using historical recovery rate.

        Args:
            df: DataFrame with 'historical_recovery_rate' column

        Returns:
            Array of predicted probabilities
        """
        if 'historical_recovery_rate' not in df.columns:
            raise ValueError("DataFrame missing 'historical_recovery_rate' column")

        scores = df['historical_recovery_rate'].values.copy()

        # Handle missing/zero history with cold-start fallback
        if self.cold_start_fallback is not None:
            # Zero history customers (historical_recovery_count == 0)
            has_no_history = (df['historical_recovery_count'] == 0)
            scores[has_no_history] = self.cold_start_fallback

        # Ensure valid probability range
        scores = np.clip(scores, 0.0, 1.0)

        return scores

    def fit(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Fit baseline model (compute cold-start fallback and threshold).

        Args:
            train_df: Training data
            val_df: Validation data

        Returns:
            Dictionary with baseline metrics
        """
        # Compute cold-start fallback from validation set
        if self.cold_start_fallback is None:
            val_recovery_rates = val_df['historical_recovery_rate'].dropna()
            self.cold_start_fallback = val_recovery_rates.mean()
            print(f"  Cold-start fallback: {self.cold_start_fallback:.4f}")

        # Predict on validation
        y_val = val_df['target'].values
        y_pred_proba = self.predict_proba(val_df)

        # Compute metrics
        metrics = {
            'roc_auc': roc_auc_score(y_val, y_pred_proba),
            'pr_auc': average_precision_score(y_val, y_pred_proba),
            'brier_score': brier_score_loss(y_val, y_pred_proba),
        }

        self.validation_metrics = metrics

        # Simple threshold selection: maximize F1 on validation
        # (Can be replaced with economic threshold in 7B)
        from sklearn.metrics import f1_score
        thresholds = np.linspace(0.0, 1.0, 101)
        f1_scores = []
        for thresh in thresholds:
            y_pred = (y_pred_proba >= thresh).astype(int)
            f1_scores.append(f1_score(y_val, y_pred, zero_division=0))

        best_idx = np.argmax(f1_scores)
        self.threshold = thresholds[best_idx]

        print(f"  Validation ROC-AUC: {metrics['roc_auc']:.4f}")
        print(f"  Validation PR-AUC: {metrics['pr_auc']:.4f}")
        print(f"  Validation Brier: {metrics['brier_score']:.4f}")
        print(f"  Selected threshold: {self.threshold:.4f}")

        return metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict binary class labels.

        Args:
            df: DataFrame with features

        Returns:
            Array of binary predictions
        """
        if self.threshold is None:
            raise ValueError("Model must be fitted before prediction")

        proba = self.predict_proba(df)
        return (proba >= self.threshold).astype(int)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize baseline model to dictionary."""
        return {
            'model_type': 'HistoricalRecoveryRateBaseline',
            'cold_start_fallback': self.cold_start_fallback,
            'threshold': self.threshold,
            'validation_metrics': self.validation_metrics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoricalRecoveryRateBaseline':
        """Load baseline model from dictionary."""
        model = cls(cold_start_fallback=data['cold_start_fallback'])
        model.threshold = data['threshold']
        model.validation_metrics = data['validation_metrics']
        return model
