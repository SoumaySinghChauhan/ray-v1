"""
Historical transaction generator.

Generates realistic payment history for each customer.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np

from simulator.world_model.customer_behavior import CustomerLatentState, CustomerBehaviorModel
from simulator.scenarios.failure_scenarios import (
    FailureScenarioGenerator,
    FailureClassType
)


@dataclass
class HistoricalTransaction:
    """A historical payment transaction."""

    transaction_id: str
    customer_id: str
    merchant_id: str
    amount: Decimal
    currency: str
    payment_method: str
    status: str  # "success" or "failed"
    failure_class: FailureClassType | None
    failure_description: str | None
    created_at: datetime
    recovered_at: datetime | None  # If failed then recovered

    # Observable features derived from recovery
    was_recovered: bool


class HistoricalTransactionGenerator:
    """Generate realistic historical payment records."""

    def __init__(self, seed: int, config, behavior_model: CustomerBehaviorModel):
        """Initialize generator."""
        self.rng = np.random.RandomState(seed)
        self.config = config
        self.behavior_model = behavior_model
        self.scenario_generator = FailureScenarioGenerator(seed + 1)

    def generate_history(
        self,
        customer: CustomerLatentState,
        merchant_id: str,
        current_timestamp: datetime,
    ) -> list[HistoricalTransaction]:
        """
        Generate 20-30 historical transactions for a customer.

        Transactions are generated chronologically before current_timestamp.
        Mix of successes and failures based on customer's hidden reliability.
        """

        # Random count between 20-30
        transaction_count = self.rng.randint(
            self.config.simulator.historical_transactions_min,
            self.config.simulator.historical_transactions_max + 1
        )

        transactions = []

        # Generate transactions going backwards in time
        # Most recent transactions closer to current_timestamp
        for i in range(transaction_count):
            transaction_id = f"txn_{customer.customer_id}_{i:03d}"

            # Time offset: exponential distribution (more recent transactions)
            # Range: 7 days to 365 days in the past
            days_ago = 7 + self.rng.exponential(scale=60)
            days_ago = min(days_ago, 365)
            created_at = current_timestamp - timedelta(days=days_ago)

            # Amount based on customer spending tier
            amount = self.behavior_model.generate_transaction_amount(
                customer,
                self.config.simulator.payment_amount_max
            )

            # Payment method
            payment_method = self.rng.choice(
                ["card", "upi", "netbanking", "wallet"],
                p=[0.50, 0.30, 0.15, 0.05]
            )

            # Determine if transaction succeeded
            # Based on customer's hidden payment reliability
            success_probability = customer.payment_reliability

            # Add some noise
            success_probability = success_probability * self.rng.uniform(0.9, 1.1)
            success_probability = np.clip(success_probability, 0.0, 1.0)

            is_success = self.rng.random() < success_probability

            if is_success:
                # Successful transaction
                transactions.append(HistoricalTransaction(
                    transaction_id=transaction_id,
                    customer_id=customer.customer_id,
                    merchant_id=merchant_id,
                    amount=amount,
                    currency="INR",
                    payment_method=payment_method,
                    status="success",
                    failure_class=None,
                    failure_description=None,
                    created_at=created_at,
                    recovered_at=None,
                    was_recovered=False,
                ))

            else:
                # Failed transaction
                scenario = self.scenario_generator.select_scenario()

                # Simple history description for failure context
                history_desc = self._generate_history_description(customer)

                failure_description = self.scenario_generator.generate_description(
                    scenario,
                    history_desc
                )

                # Determine if this failure was eventually recovered
                # Based on customer's hidden recovery affinity
                recovery_probability = (
                    customer.recovery_affinity
                    * scenario.payment_link_recovery_modifier
                    * 0.5  # Historical recovery rate lower
                )
                recovery_probability = np.clip(recovery_probability, 0.0, 0.8)

                was_recovered = self.rng.random() < recovery_probability

                recovered_at = None
                if was_recovered:
                    # Recovery happened 1-7 days after failure
                    recovery_days = self.rng.uniform(1, min(7, scenario.typical_recovery_window_hours / 24))
                    recovered_at = created_at + timedelta(days=recovery_days)

                transactions.append(HistoricalTransaction(
                    transaction_id=transaction_id,
                    customer_id=customer.customer_id,
                    merchant_id=merchant_id,
                    amount=amount,
                    currency="INR",
                    payment_method=payment_method,
                    status="failed",
                    failure_class=scenario.failure_class,
                    failure_description=failure_description,
                    created_at=created_at,
                    recovered_at=recovered_at,
                    was_recovered=was_recovered,
                ))

        # Sort chronologically
        transactions.sort(key=lambda t: t.created_at)

        return transactions

    def _generate_history_description(self, customer: CustomerLatentState) -> str:
        """Generate simple description of customer history for failure messages."""
        if customer.customer_maturity == "new":
            return "few previous transactions"
        elif customer.customer_maturity == "regular":
            return "completed several previous payments"
        else:  # established
            return "a strong payment history"
