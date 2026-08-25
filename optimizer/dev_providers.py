"""
Development fixtures for optimizer testing.

CRITICAL: These are DEVELOPMENT FIXTURES ONLY.
They are NOT production models and must NOT appear in final benchmark results.

Purpose: Enable optimizer testing without requiring frozen ML models.
"""

from typing import Any
from optimizer.interfaces import (
    RecoveryProbabilityProvider,
    ActionEligibilityProvider,
    ActionEligibility,
)


class DevelopmentRecoveryProbabilityProvider(RecoveryProbabilityProvider):
    """
    Deterministic development fixture for recovery probability prediction.

    DEVELOPMENT FIXTURE ONLY - NOT A PRODUCTION MODEL

    Uses ONLY observable features:
    - failure_class
    - amount
    - historical_recovery_rate
    - historical_success_rate
    - avg_payment_amount

    Does NOT use:
    - true_payment_link_probability (hidden ground truth)
    - true_organic_probability (hidden ground truth)
    - customer latent traits (hidden simulator variables)
    - ground truth outcomes
    """

    def predict_payment_link_probability(self, opportunity: dict[str, Any]) -> float:
        """
        Deterministic fixture prediction based on observable features.

        Formula:
        - Base from failure class (hard decline = low, soft decline = high)
        - Adjusted by historical recovery rate
        - Adjusted by historical success rate
        - Adjusted by payment value relative to average

        Returns:
            Probability in [0.0, 1.0]
        """
        # Base probability from failure class
        failure_class = opportunity.get("failure_class", "unknown")

        if failure_class == "soft_decline":
            base_prob = 0.45
        elif failure_class == "hard_decline":
            base_prob = 0.15
        elif failure_class == "authentication_failure":
            base_prob = 0.30
        elif failure_class == "gateway_error":
            base_prob = 0.25
        else:
            base_prob = 0.20

        # Adjust by customer history
        historical_recovery_rate = opportunity.get("historical_recovery_rate", 0.0)
        historical_success_rate = opportunity.get("historical_success_rate", 0.0)

        # If customer has good recovery history, boost probability
        recovery_adjustment = historical_recovery_rate * 0.3

        # If customer has good success history, boost probability
        success_adjustment = historical_success_rate * 0.2

        # Adjust by payment value
        amount = opportunity.get("amount", 0.0)
        avg_amount = opportunity.get("avg_payment_amount", amount)

        if avg_amount > 0:
            value_ratio = amount / avg_amount
            # Higher value relative to average slightly increases probability
            # (more motivation to recover)
            if value_ratio > 1.5:
                value_adjustment = 0.05
            elif value_ratio < 0.5:
                value_adjustment = -0.05
            else:
                value_adjustment = 0.0
        else:
            value_adjustment = 0.0

        # Combine adjustments
        final_prob = base_prob + recovery_adjustment + success_adjustment + value_adjustment

        # Bound to [0, 1]
        final_prob = max(0.0, min(1.0, final_prob))

        return final_prob


class DevelopmentEligibilityProvider(ActionEligibilityProvider):
    """
    Simple development fixture for action eligibility.

    DEVELOPMENT FIXTURE ONLY - NOT PRODUCTION POLICY ENGINE

    Basic rules:
    - payment_link: check not in do-not-contact (simulated)
    - do_nothing: always eligible
    """

    def check_eligibility(
        self, opportunity: dict[str, Any], action: str
    ) -> ActionEligibility:
        """
        Deterministic fixture eligibility check.

        Simple rule: All opportunities eligible for development testing.
        Production policy engine will implement real constraints.

        Returns:
            ActionEligibility.ELIGIBLE (all opportunities for dev testing)
        """
        # In development, make all opportunities eligible
        # Real policy engine (Prompt 5) will implement actual constraints:
        # - do-not-contact
        # - contact frequency caps
        # - amount limits
        # - etc.

        if action == "do_nothing":
            # do_nothing always eligible
            return ActionEligibility.ELIGIBLE

        elif action == "create_payment_link":
            # For development: all eligible
            # Real policy would check:
            # - customer not in DNC list
            # - contact frequency within limits
            # - amount within autonomous limits
            return ActionEligibility.ELIGIBLE

        else:
            # Unknown action: ineligible
            return ActionEligibility.INELIGIBLE
