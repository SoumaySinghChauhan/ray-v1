"""
Optimizer interfaces for RAY V1.

These interfaces enforce clean separation between:
- Prediction (probability estimation)
- Policy (eligibility determination)
- Optimization (economic decision making)
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class ActionEligibility(str, Enum):
    """Action eligibility status from policy engine."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class RecoveryProbabilityProvider(ABC):
    """
    Interface for recovery probability prediction.

    The optimizer depends on this interface, NOT on specific ML models.
    """

    @abstractmethod
    def predict_payment_link_probability(self, opportunity: dict[str, Any]) -> float:
        """
        Predict probability of recovery if payment link is created.

        Args:
            opportunity: Observable opportunity features

        Returns:
            Probability in [0.0, 1.0]

        Raises:
            ValueError: If prediction cannot be made
        """
        pass


class ActionEligibilityProvider(ABC):
    """
    Interface for action eligibility determination.

    The optimizer depends on this interface, NOT on specific policy logic.
    """

    @abstractmethod
    def check_eligibility(
        self, opportunity: dict[str, Any], action: str
    ) -> ActionEligibility:
        """
        Check if action is eligible for opportunity.

        Args:
            opportunity: Observable opportunity features
            action: Action to check (create_payment_link or do_nothing)

        Returns:
            ActionEligibility status
        """
        pass
