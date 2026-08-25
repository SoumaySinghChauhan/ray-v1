"""
Payment failure scenarios with ground truth probabilities.

Each scenario defines:
1. Observable failure information (what RAY sees)
2. Hidden ground truth (true recovery probabilities)
"""

from dataclasses import dataclass
from typing import Literal
import numpy as np


FailureClassType = Literal[
    "soft_decline",
    "hard_decline",
    "authentication_failure",
    "gateway_error",
    "unknown"
]


@dataclass
class FailureScenarioDefinition:
    """
    Defines a failure scenario with observable and hidden components.

    Observable: failure_class, description_template
    Hidden: base probability modifiers
    """

    scenario_id: str  # HIDDEN - never exposed
    failure_class: FailureClassType  # OBSERVABLE
    description_template: str  # OBSERVABLE (with variation)

    # Hidden ground truth probability modifiers
    # These adjust base recovery probability based on failure type
    organic_recovery_modifier: float  # Multiplier for organic recovery
    payment_link_recovery_modifier: float  # Multiplier for payment link recovery

    # Hidden issuer behavior
    typical_recovery_window_hours: int  # How long before natural resolution

    def __post_init__(self):
        """Validate scenario."""
        assert 0.0 <= self.organic_recovery_modifier <= 2.0
        assert 0.0 <= self.payment_link_recovery_modifier <= 2.0


# V1 Failure Scenario Registry
FAILURE_SCENARIOS: list[FailureScenarioDefinition] = [
    # ========================================================================
    # SOFT DECLINES - Higher recovery potential
    # ========================================================================
    FailureScenarioDefinition(
        scenario_id="soft_insufficient_funds",
        failure_class="soft_decline",
        description_template="The issuing bank declined the transaction due to insufficient funds. Customer has {history_desc}.",
        organic_recovery_modifier=0.8,
        payment_link_recovery_modifier=1.4,
        typical_recovery_window_hours=48,
    ),
    FailureScenarioDefinition(
        scenario_id="soft_temporary_decline",
        failure_class="soft_decline",
        description_template="Transaction temporarily declined by issuing bank. Customer previously {history_desc}.",
        organic_recovery_modifier=0.9,
        payment_link_recovery_modifier=1.3,
        typical_recovery_window_hours=24,
    ),
    FailureScenarioDefinition(
        scenario_id="soft_risk_threshold",
        failure_class="soft_decline",
        description_template="Transaction flagged for risk review by issuer. Customer has {history_desc}.",
        organic_recovery_modifier=0.7,
        payment_link_recovery_modifier=1.2,
        typical_recovery_window_hours=72,
    ),

    # ========================================================================
    # HARD DECLINES - Lower recovery potential
    # ========================================================================
    FailureScenarioDefinition(
        scenario_id="hard_invalid_card",
        failure_class="hard_decline",
        description_template="Card declined as invalid or expired. Customer {history_desc}.",
        organic_recovery_modifier=0.3,
        payment_link_recovery_modifier=0.7,
        typical_recovery_window_hours=168,  # 7 days
    ),
    FailureScenarioDefinition(
        scenario_id="hard_stolen_card",
        failure_class="hard_decline",
        description_template="Payment instrument reported lost or stolen. Customer has {history_desc}.",
        organic_recovery_modifier=0.2,
        payment_link_recovery_modifier=0.8,
        typical_recovery_window_hours=240,  # 10 days
    ),
    FailureScenarioDefinition(
        scenario_id="hard_closed_account",
        failure_class="hard_decline",
        description_template="Issuing bank reports account closed or restricted. Customer previously {history_desc}.",
        organic_recovery_modifier=0.1,
        payment_link_recovery_modifier=0.5,
        typical_recovery_window_hours=336,  # 14 days
    ),

    # ========================================================================
    # AUTHENTICATION FAILURES - Medium recovery potential
    # ========================================================================
    FailureScenarioDefinition(
        scenario_id="auth_3ds_failure",
        failure_class="authentication_failure",
        description_template="3D Secure authentication failed or timed out. Customer {history_desc}.",
        organic_recovery_modifier=0.5,
        payment_link_recovery_modifier=1.1,
        typical_recovery_window_hours=48,
    ),
    FailureScenarioDefinition(
        scenario_id="auth_verification_required",
        failure_class="authentication_failure",
        description_template="Additional verification required by issuing bank. Customer has {history_desc}.",
        organic_recovery_modifier=0.6,
        payment_link_recovery_modifier=1.0,
        typical_recovery_window_hours=72,
    ),

    # ========================================================================
    # GATEWAY ERRORS - Variable recovery potential
    # ========================================================================
    FailureScenarioDefinition(
        scenario_id="gateway_timeout",
        failure_class="gateway_error",
        description_template="Payment gateway timeout during processing. Customer previously {history_desc}.",
        organic_recovery_modifier=1.0,
        payment_link_recovery_modifier=1.3,
        typical_recovery_window_hours=1,  # Very short - technical issue
    ),
    FailureScenarioDefinition(
        scenario_id="gateway_network_error",
        failure_class="gateway_error",
        description_template="Network connectivity issue during payment processing. Customer {history_desc}.",
        organic_recovery_modifier=0.9,
        payment_link_recovery_modifier=1.2,
        typical_recovery_window_hours=2,
    ),

    # ========================================================================
    # UNKNOWN - Conservative assumptions
    # ========================================================================
    FailureScenarioDefinition(
        scenario_id="unknown_decline",
        failure_class="unknown",
        description_template="Payment declined for unspecified reason. Customer has {history_desc}.",
        organic_recovery_modifier=0.5,
        payment_link_recovery_modifier=0.9,
        typical_recovery_window_hours=96,
    ),
]


class FailureScenarioGenerator:
    """Generate failure scenarios with realistic variation."""

    def __init__(self, seed: int):
        """Initialize with reproducible random state."""
        self.rng = np.random.RandomState(seed)

    def select_scenario(self) -> FailureScenarioDefinition:
        """
        Select a failure scenario with realistic distribution.

        Soft declines are most common, hard declines less common.
        """
        # Realistic distribution weights
        weights = []
        for scenario in FAILURE_SCENARIOS:
            if scenario.failure_class == "soft_decline":
                weight = 0.40  # 40% soft declines
            elif scenario.failure_class == "hard_decline":
                weight = 0.25  # 25% hard declines
            elif scenario.failure_class == "authentication_failure":
                weight = 0.15  # 15% auth failures
            elif scenario.failure_class == "gateway_error":
                weight = 0.10  # 10% gateway errors
            else:  # unknown
                weight = 0.10  # 10% unknown
            weights.append(weight)

        # Normalize weights
        weights = np.array(weights)
        weights = weights / weights.sum()

        scenario_idx = self.rng.choice(len(FAILURE_SCENARIOS), p=weights)
        return FAILURE_SCENARIOS[scenario_idx]

    def generate_description(
        self,
        scenario: FailureScenarioDefinition,
        customer_history_summary: str
    ) -> str:
        """
        Generate observable failure description.

        CRITICAL: Does NOT expose scenario_id or hidden variables.
        Only exposes human-readable description.
        """
        description = scenario.description_template.format(
            history_desc=customer_history_summary
        )

        # Add realistic variation
        variations = [
            "",
            " Please retry payment.",
            " Contact your bank for details.",
            " You may use an alternate payment method.",
        ]
        variation = self.rng.choice(variations)

        return description + variation
