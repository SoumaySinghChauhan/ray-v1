"""
Ground truth probability model.

THIS MODULE CONTAINS THE SIMULATOR'S TRUTH.

These probabilities represent the actual recovery behavior in the synthetic world.
They are NEVER exposed to RAY's production decision logic.

The ML model will attempt to predict these probabilities from observable features.
The simulator defines reality. The ML model predicts reality.
"""

from dataclasses import dataclass
from decimal import Decimal
import numpy as np

from simulator.world_model.customer_behavior import CustomerLatentState
from simulator.scenarios.failure_scenarios import FailureScenarioDefinition


@dataclass
class GroundTruthOutcome:
    """
    Hidden ground truth for a recovery opportunity.

    NEVER exposed to production decision logic.
    Used only by simulator and evaluation.
    """

    opportunity_id: str

    # True recovery probabilities (HIDDEN)
    true_organic_recovery_probability: float
    true_payment_link_recovery_probability: float

    # Hidden scenario information
    scenario_id: str
    scenario_failure_class: str

    # Hidden customer state
    customer_payment_reliability: float
    customer_recovery_affinity: float
    customer_contact_responsiveness: float

    def __post_init__(self):
        """Validate ground truth."""
        assert 0.0 <= self.true_organic_recovery_probability <= 1.0
        assert 0.0 <= self.true_payment_link_recovery_probability <= 1.0


class GroundTruthProbabilityModel:
    """
    Calculate true recovery probabilities from hidden state.

    This is the simulator's oracle. It knows the truth.
    RAY never gets to see these probabilities directly.
    """

    def __init__(self, seed: int, config):
        """Initialize ground truth model."""
        self.rng = np.random.RandomState(seed)
        self.config = config

    def calculate_ground_truth(
        self,
        opportunity_id: str,
        customer: CustomerLatentState,
        scenario: FailureScenarioDefinition,
        amount: Decimal,
        hours_since_failure: int,
        historical_recovery_rate: float,
        historical_payment_count: int,
    ) -> GroundTruthOutcome:
        """
        Calculate TRUE recovery probabilities.

        These depend on:
        - Hidden customer traits
        - Failure scenario
        - Observable features (amount, history, time)

        The formula is synthetic but realistic - multiple factors contribute.
        """

        # ====================================================================
        # BASE ORGANIC RECOVERY PROBABILITY
        # ====================================================================

        # Start with configured baseline (4%)
        base_organic = self.config.recovery.assumed_organic_recovery_rate

        # Adjust by customer's hidden recovery affinity
        organic_customer_factor = 0.3 + (1.4 * customer.recovery_affinity)

        # Adjust by failure scenario
        organic_scenario_factor = scenario.organic_recovery_modifier

        # Adjust by amount (higher amounts slightly less likely to self-resolve)
        amount_factor = 1.0 - (0.0001 * min(float(amount), 50000))

        # Adjust by time (organic recovery less likely as time passes)
        time_decay = np.exp(-hours_since_failure / 48.0)

        # Combine factors
        organic_prob = (
            base_organic
            * organic_customer_factor
            * organic_scenario_factor
            * amount_factor
            * time_decay
        )

        # Add realistic noise
        organic_prob = organic_prob * self.rng.uniform(0.8, 1.2)

        # Clip to valid range
        organic_prob = float(np.clip(organic_prob, 0.01, 0.25))

        # ====================================================================
        # BASE PAYMENT LINK RECOVERY PROBABILITY
        # ====================================================================

        # Start higher than organic - intervention is helpful
        base_payment_link = 0.35

        # Adjust by customer's hidden traits
        customer_reliability_factor = 0.5 + (1.0 * customer.payment_reliability)
        customer_recovery_factor = 0.4 + (1.2 * customer.recovery_affinity)
        customer_responsiveness_factor = 0.5 + (1.0 * customer.contact_responsiveness)

        customer_factor = (
            customer_reliability_factor *
            customer_recovery_factor *
            customer_responsiveness_factor
        ) / 3.0

        # Adjust by failure scenario
        scenario_factor = scenario.payment_link_recovery_modifier

        # Adjust by historical success
        # Customers with good history respond better
        history_factor = 0.7 + (0.6 * min(historical_recovery_rate, 1.0))

        # Adjust by customer maturity (established customers more responsive)
        if customer.customer_maturity == "established":
            maturity_factor = 1.2
        elif customer.customer_maturity == "regular":
            maturity_factor = 1.0
        else:  # new
            maturity_factor = 0.85

        # Adjust by amount (higher amounts have better attention)
        if float(amount) > 5000:
            amount_factor = 1.1
        elif float(amount) < 500:
            amount_factor = 0.9
        else:
            amount_factor = 1.0

        # Combine factors
        payment_link_prob = (
            base_payment_link
            * customer_factor
            * scenario_factor
            * history_factor
            * maturity_factor
            * amount_factor
        )

        # Add realistic noise
        payment_link_prob = payment_link_prob * self.rng.uniform(0.85, 1.15)

        # Clip to valid range
        payment_link_prob = float(np.clip(payment_link_prob, 0.05, 0.85))

        # ====================================================================
        # ENSURE PAYMENT LINK >= ORGANIC
        # ====================================================================

        # Payment link should generally be at least as good as organic
        # (occasionally it might not be if customer is unresponsive)
        if customer.contact_responsiveness > 0.3:
            payment_link_prob = max(payment_link_prob, organic_prob)

        # ====================================================================
        # RETURN GROUND TRUTH
        # ====================================================================

        return GroundTruthOutcome(
            opportunity_id=opportunity_id,
            true_organic_recovery_probability=organic_prob,
            true_payment_link_recovery_probability=payment_link_prob,
            scenario_id=scenario.scenario_id,
            scenario_failure_class=scenario.failure_class,
            customer_payment_reliability=customer.payment_reliability,
            customer_recovery_affinity=customer.recovery_affinity,
            customer_contact_responsiveness=customer.contact_responsiveness,
        )

    def simulate_outcome(
        self,
        ground_truth: GroundTruthOutcome,
        action_taken: str
    ) -> bool:
        """
        Simulate actual recovery outcome based on ground truth.

        This is what ACTUALLY happens in the synthetic world.

        Args:
            ground_truth: Hidden true probabilities
            action_taken: "payment_link" or "do_nothing"

        Returns:
            True if recovery occurred, False otherwise
        """
        if action_taken == "payment_link":
            prob = ground_truth.true_payment_link_recovery_probability
        elif action_taken == "do_nothing":
            prob = ground_truth.true_organic_recovery_probability
        else:
            raise ValueError(f"Unknown action: {action_taken}")

        # Simulate bernoulli outcome
        return self.rng.random() < prob
