"""
RAY V1 Baseline Implementation.

Baseline uses customer historical recovery rate to predict payment link success.
"""

import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Any


class BaselinePredictor:
    """
    Baseline recovery probability predictor.

    Uses customer historical recovery rate as the prediction.
    """

    def __init__(self, cold_start_fallback: float | None = None):
        """
        Initialize baseline predictor.

        Args:
            cold_start_fallback: Fallback probability for customers with zero
                historical failures. If None, calculated from validation data.
        """
        self.cold_start_fallback = cold_start_fallback
        self.is_fitted = cold_start_fallback is not None

    def fit(self, df_validation: pd.DataFrame) -> "BaselinePredictor":
        """
        Fit baseline model on validation data.

        Calculates cold-start fallback as mean historical recovery rate
        among validation customers who have at least one historical failure.

        Args:
            df_validation: Validation dataframe with historical_recovery_rate

        Returns:
            self
        """

        # Calculate fallback from customers with history
        customers_with_failures = df_validation[
            df_validation["historical_failure_count"] > 0
        ]

        if len(customers_with_failures) == 0:
            raise ValueError("No validation customers with failure history")

        self.cold_start_fallback = float(
            customers_with_failures["historical_recovery_rate"].mean()
        )

        self.is_fitted = True

        print(f"Baseline cold-start fallback: {self.cold_start_fallback:.4f}")

        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict recovery probabilities.

        Args:
            df: DataFrame with historical_recovery_rate and
                historical_failure_count columns

        Returns:
            Array of predicted probabilities

        Raises:
            RuntimeError: If not fitted
        """

        if not self.is_fitted:
            raise RuntimeError("Baseline not fitted. Call fit() first.")

        # Use historical recovery rate, with fallback for cold start
        probabilities = np.where(
            df["historical_failure_count"] > 0,
            df["historical_recovery_rate"],
            self.cold_start_fallback,
        )

        return probabilities

    def calculate_score(
        self,
        df: pd.DataFrame,
        probability_col: str = "baseline_probability"
    ) -> pd.DataFrame:
        """
        Calculate baseline score for ranking.

        Score = probability × amount

        Args:
            df: DataFrame with predictions and amounts
            probability_col: Name of probability column

        Returns:
            DataFrame with baseline_score added
        """

        df = df.copy()
        df["baseline_score"] = df[probability_col] * df["amount"]
        return df

    def to_dict(self) -> dict[str, Any]:
        """Export baseline configuration."""
        return {
            "baseline_type": "historical_recovery_rate",
            "cold_start_fallback": self.cold_start_fallback,
            "is_fitted": self.is_fitted,
        }

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "BaselinePredictor":
        """Load baseline from configuration."""
        return cls(cold_start_fallback=config["cold_start_fallback"])
