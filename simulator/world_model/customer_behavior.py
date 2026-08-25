"""
Customer behavior model for synthetic world generation.

This module generates synthetic customers with hidden behavioral traits.
These traits influence payment and recovery behavior but are NEVER
exposed as features to the ML model.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
import numpy as np


@dataclass
class CustomerLatentState:
    """
    Hidden customer behavioral traits.

    These variables represent the TRUE underlying customer behavior.
    They are NEVER exposed to RAY's production decision logic.
    """

    customer_id: str

    # Hidden behavioral propensities (0.0 to 1.0)
    payment_reliability: float  # Baseline payment success tendency
    recovery_affinity: float    # Tendency to recover after failure
    contact_responsiveness: float  # Response to recovery interventions

    # Hidden spending behavior
    spending_tier: Literal["low", "medium", "high"]

    # Hidden customer lifecycle
    customer_maturity: Literal["new", "regular", "established"]

    def __post_init__(self):
        """Validate hidden state."""
        assert 0.0 <= self.payment_reliability <= 1.0
        assert 0.0 <= self.recovery_affinity <= 1.0
        assert 0.0 <= self.contact_responsiveness <= 1.0


class CustomerBehaviorModel:
    """Generate synthetic customers with realistic heterogeneity."""

    def __init__(self, seed: int):
        """Initialize with reproducible random state."""
        self.rng = np.random.RandomState(seed)

    def generate_customers(self, count: int) -> list[CustomerLatentState]:
        """
        Generate synthetic customers with hidden behavioral traits.

        Creates realistic heterogeneity across:
        - Payment reliability
        - Recovery affinity
        - Contact responsiveness
        - Spending tiers
        - Customer maturity
        """
        customers = []

        for i in range(count):
            customer_id = f"cust_{i:06d}"

            # Determine customer archetype
            archetype = self.rng.choice([
                "reliable_high_value",
                "regular_mid_value",
                "new_low_history",
                "frequent_failer",
                "recovered_previously",
            ], p=[0.20, 0.35, 0.15, 0.15, 0.15])

            # Generate traits based on archetype with noise
            if archetype == "reliable_high_value":
                payment_reliability = self._bounded_normal(0.85, 0.10)
                recovery_affinity = self._bounded_normal(0.75, 0.15)
                contact_responsiveness = self._bounded_normal(0.70, 0.15)
                spending_tier = self.rng.choice(["medium", "high"], p=[0.3, 0.7])
                customer_maturity = self.rng.choice(["regular", "established"], p=[0.4, 0.6])

            elif archetype == "regular_mid_value":
                payment_reliability = self._bounded_normal(0.70, 0.15)
                recovery_affinity = self._bounded_normal(0.55, 0.20)
                contact_responsiveness = self._bounded_normal(0.55, 0.20)
                spending_tier = self.rng.choice(["low", "medium", "high"], p=[0.2, 0.6, 0.2])
                customer_maturity = "regular"

            elif archetype == "new_low_history":
                payment_reliability = self._bounded_normal(0.60, 0.20)
                recovery_affinity = self._bounded_normal(0.45, 0.25)
                contact_responsiveness = self._bounded_normal(0.50, 0.25)
                spending_tier = self.rng.choice(["low", "medium"], p=[0.7, 0.3])
                customer_maturity = "new"

            elif archetype == "frequent_failer":
                payment_reliability = self._bounded_normal(0.40, 0.15)
                recovery_affinity = self._bounded_normal(0.35, 0.20)
                contact_responsiveness = self._bounded_normal(0.40, 0.20)
                spending_tier = self.rng.choice(["low", "medium"], p=[0.6, 0.4])
                customer_maturity = self.rng.choice(["new", "regular"], p=[0.5, 0.5])

            else:  # recovered_previously
                payment_reliability = self._bounded_normal(0.65, 0.15)
                recovery_affinity = self._bounded_normal(0.65, 0.15)
                contact_responsiveness = self._bounded_normal(0.65, 0.15)
                spending_tier = self.rng.choice(["low", "medium", "high"], p=[0.3, 0.5, 0.2])
                customer_maturity = self.rng.choice(["regular", "established"], p=[0.7, 0.3])

            customers.append(CustomerLatentState(
                customer_id=customer_id,
                payment_reliability=payment_reliability,
                recovery_affinity=recovery_affinity,
                contact_responsiveness=contact_responsiveness,
                spending_tier=spending_tier,
                customer_maturity=customer_maturity,
            ))

        return customers

    def _bounded_normal(self, mean: float, std: float) -> float:
        """Sample from normal distribution bounded to [0, 1]."""
        value = self.rng.normal(mean, std)
        return float(np.clip(value, 0.0, 1.0))

    def generate_transaction_amount(
        self,
        customer: CustomerLatentState,
        max_amount: Decimal
    ) -> Decimal:
        """
        Generate realistic transaction amount based on customer spending tier.

        Uses log-normal distribution with tier-dependent parameters.
        """
        # Base parameters by spending tier
        if customer.spending_tier == "low":
            mean_log = 6.5  # ~₹665
            std_log = 0.8
        elif customer.spending_tier == "medium":
            mean_log = 7.5  # ~₹1,808
            std_log = 0.9
        else:  # high
            mean_log = 8.5  # ~₹4,914
            std_log = 1.0

        # Sample from log-normal
        amount = self.rng.lognormal(mean_log, std_log)

        # Cap at max and round
        amount = min(amount, float(max_amount))
        amount = max(amount, 50.0)  # Minimum ₹50

        return Decimal(str(round(amount, 2)))
