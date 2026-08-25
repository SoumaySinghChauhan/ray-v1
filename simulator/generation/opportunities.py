"""
Current opportunity generator.

Generates payment failure opportunities for evaluation.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
import numpy as np

from simulator.world_model.customer_behavior import CustomerLatentState, CustomerBehaviorModel
from simulator.scenarios.failure_scenarios import (
    FailureScenarioGenerator,
    FailureScenarioDefinition,
)
from simulator.generation.historical_transactions import HistoricalTransaction


@dataclass
class CurrentOpportunity:
    """
    A current payment failure opportunity.

    Contains ONLY observable information.
    Hidden ground truth is stored separately.
    """

    opportunity_id: str
    customer_id: str
    merchant_id: str
    payment_id: str

    # Observable payment details
    amount: Decimal
    currency: str
    payment_method: str

    # Observable failure information
    failure_class: str
    failure_description: str

    # Observable timing
    created_at: datetime
    hours_since_failure: int
    simulated_day: int

    # Observable attempt counts
    retry_count: int
    contact_count: int

    # Observable customer history (calculated from historical transactions)
    historical_payment_count: int
    historical_success_count: int
    historical_failure_count: int
    historical_recovery_count: int
    historical_recovery_rate: float
    customer_lifetime_value: Decimal
    avg_payment_amount: Decimal
    days_since_first_payment: int

    # Data split assignment
    split: Literal["train", "validation", "test"]


class OpportunityGenerator:
    """Generate current payment failure opportunities."""

    def __init__(
        self,
        seed: int,
        config,
        behavior_model: CustomerBehaviorModel,
        scenario_generator: FailureScenarioGenerator,
    ):
        """Initialize generator."""
        self.rng = np.random.RandomState(seed)
        self.config = config
        self.behavior_model = behavior_model
        self.scenario_generator = scenario_generator

    def generate_opportunity(
        self,
        opportunity_idx: int,
        customer: CustomerLatentState,
        merchant_id: str,
        historical_transactions: list[HistoricalTransaction],
        simulated_day: int,
        base_timestamp: datetime,
    ) -> tuple[CurrentOpportunity, FailureScenarioDefinition]:
        """
        Generate a single current opportunity.

        Returns both:
        - Observable opportunity data
        - Hidden scenario definition (for ground truth calculation)
        """

        opportunity_id = f"opp_{opportunity_idx:06d}"
        payment_id = f"pay_{opportunity_idx:06d}"

        # Generate payment details
        amount = self.behavior_model.generate_transaction_amount(
            customer,
            self.config.simulator.payment_amount_max
        )

        payment_method = self.rng.choice(
            ["card", "upi", "netbanking", "wallet"],
            p=[0.50, 0.30, 0.15, 0.05]
        )

        # Select failure scenario
        scenario = self.scenario_generator.select_scenario()

        # Calculate observable customer history
        history_features = self._calculate_history_features(
            historical_transactions,
            base_timestamp
        )

        # Generate history description for failure message
        history_desc = self._generate_history_description(history_features)

        failure_description = self.scenario_generator.generate_description(
            scenario,
            history_desc
        )

        # Simulated timestamp for this day
        # Add random hour within the day
        hour_offset = self.rng.uniform(0, 24)
        created_at = base_timestamp + timedelta(days=simulated_day - 1, hours=hour_offset)

        # Hours since failure (for evaluation, all opportunities start fresh)
        hours_since_failure = self.rng.randint(1, 6)

        # Retry and contact counts (most opportunities are first contact)
        retry_count = 0  # V1: all are first opportunity
        contact_count = 0  # V1: no prior contact

        return (
            CurrentOpportunity(
                opportunity_id=opportunity_id,
                customer_id=customer.customer_id,
                merchant_id=merchant_id,
                payment_id=payment_id,
                amount=amount,
                currency="INR",
                payment_method=payment_method,
                failure_class=scenario.failure_class,
                failure_description=failure_description,
                created_at=created_at,
                hours_since_failure=hours_since_failure,
                simulated_day=simulated_day,
                retry_count=retry_count,
                contact_count=contact_count,
                historical_payment_count=history_features["historical_payment_count"],
                historical_success_count=history_features["historical_success_count"],
                historical_failure_count=history_features["historical_failure_count"],
                historical_recovery_count=history_features["historical_recovery_count"],
                historical_recovery_rate=history_features["historical_recovery_rate"],
                customer_lifetime_value=history_features["customer_lifetime_value"],
                avg_payment_amount=history_features["avg_payment_amount"],
                days_since_first_payment=history_features["days_since_first_payment"],
                split="train",  # Assigned later
            ),
            scenario,  # Return hidden scenario for ground truth
        )

    def _calculate_history_features(
        self,
        transactions: list[HistoricalTransaction],
        current_timestamp: datetime,
    ) -> dict:
        """
        Calculate observable customer history features.

        These are derived from past transactions and are OBSERVABLE.
        """

        if not transactions:
            # Edge case: no history (shouldn't happen in V1)
            return {
                "historical_payment_count": 0,
                "historical_success_count": 0,
                "historical_failure_count": 0,
                "historical_recovery_count": 0,
                "historical_recovery_rate": 0.0,
                "customer_lifetime_value": Decimal("0"),
                "avg_payment_amount": Decimal("0"),
                "days_since_first_payment": 0,
            }

        total_count = len(transactions)
        success_count = sum(1 for t in transactions if t.status == "success")
        failure_count = sum(1 for t in transactions if t.status == "failed")
        recovery_count = sum(1 for t in transactions if t.was_recovered)

        # Recovery rate: recoveries / failures (with Laplace smoothing for cold start)
        if failure_count > 0:
            recovery_rate = recovery_count / failure_count
        else:
            recovery_rate = 0.0

        # Customer lifetime value: sum of successful payments
        lifetime_value = sum(
            t.amount for t in transactions if t.status == "success"
        )

        # Average payment amount
        avg_amount = sum(t.amount for t in transactions) / total_count

        # Days since first payment
        first_payment = min(t.created_at for t in transactions)
        days_since_first = (current_timestamp - first_payment).days

        return {
            "historical_payment_count": total_count,
            "historical_success_count": success_count,
            "historical_failure_count": failure_count,
            "historical_recovery_count": recovery_count,
            "historical_recovery_rate": recovery_rate,
            "customer_lifetime_value": lifetime_value,
            "avg_payment_amount": avg_amount,
            "days_since_first_payment": days_since_first,
        }

    def _generate_history_description(self, history_features: dict) -> str:
        """Generate history description for failure message context."""
        total = history_features["historical_payment_count"]
        success = history_features["historical_success_count"]
        recovery_rate = history_features["historical_recovery_rate"]

        if total == 0:
            return "no previous payment history"
        elif total < 10:
            return "few previous transactions"
        elif success / total > 0.8:
            return "a strong history of successful payments"
        elif recovery_rate > 0.6:
            return "previously recovered from payment failures"
        else:
            return "completed several previous payments"

    def assign_splits(
        self,
        opportunities: list[CurrentOpportunity],
        split_seed: int,
    ) -> list[CurrentOpportunity]:
        """
        Assign train/validation/test splits by customer.

        Critical: Same customer NEVER appears in multiple splits.

        Args:
            opportunities: List of opportunities (1 per customer)
            split_seed: Seed for reproducible split

        Returns:
            Opportunities with split field assigned
        """

        # Verify exactly one opportunity per customer
        customer_ids = [opp.customer_id for opp in opportunities]
        assert len(customer_ids) == len(set(customer_ids)), \
            "Multiple opportunities per customer detected"

        # Shuffle with fixed seed
        rng = np.random.RandomState(split_seed)
        indices = np.arange(len(opportunities))
        rng.shuffle(indices)

        # Assign splits
        train_count = self.config.simulator.train_customers
        val_count = self.config.simulator.validation_customers
        test_count = self.config.simulator.test_customers

        assert train_count + val_count + test_count == len(opportunities), \
            f"Split counts don't match opportunity count"

        for i, idx in enumerate(indices):
            if i < train_count:
                split = "train"
            elif i < train_count + val_count:
                split = "validation"
            else:
                split = "test"

            # Create new opportunity with split assigned
            opp = opportunities[idx]
            opportunities[idx] = CurrentOpportunity(
                opportunity_id=opp.opportunity_id,
                customer_id=opp.customer_id,
                merchant_id=opp.merchant_id,
                payment_id=opp.payment_id,
                amount=opp.amount,
                currency=opp.currency,
                payment_method=opp.payment_method,
                failure_class=opp.failure_class,
                failure_description=opp.failure_description,
                created_at=opp.created_at,
                hours_since_failure=opp.hours_since_failure,
                simulated_day=opp.simulated_day,
                retry_count=opp.retry_count,
                contact_count=opp.contact_count,
                historical_payment_count=opp.historical_payment_count,
                historical_success_count=opp.historical_success_count,
                historical_failure_count=opp.historical_failure_count,
                historical_recovery_count=opp.historical_recovery_count,
                historical_recovery_rate=opp.historical_recovery_rate,
                customer_lifetime_value=opp.customer_lifetime_value,
                avg_payment_amount=opp.avg_payment_amount,
                days_since_first_payment=opp.days_since_first_payment,
                split=split,
            )

        return opportunities
