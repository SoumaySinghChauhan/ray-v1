"""
RAY V1 Constrained Recovery Optimizer.

Maximizes expected incremental recovery while respecting merchant constraints.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from optimizer.interfaces import (
    RecoveryProbabilityProvider,
    ActionEligibilityProvider,
    ActionEligibility,
)


class ActionType(str, Enum):
    """Valid recovery actions."""

    CREATE_PAYMENT_LINK = "create_payment_link"
    DO_NOTHING = "do_nothing"


class SkipReason(str, Enum):
    """Constrained vocabulary for skip reasons."""

    NEGATIVE_INCREMENTAL_VALUE = "NEGATIVE_INCREMENTAL_VALUE"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    INELIGIBLE = "INELIGIBLE"
    INVALID_PREDICTION = "INVALID_PREDICTION"
    EXPIRED_OPPORTUNITY = "EXPIRED_OPPORTUNITY"
    DUPLICATE_OPPORTUNITY = "DUPLICATE_OPPORTUNITY"


@dataclass
class OpportunityDecision:
    """Decision for a single opportunity."""

    opportunity_id: str
    selected_action: str
    payment_link_probability: float
    assumed_organic_probability: float
    payment_link_ev: float
    do_nothing_ev: float
    incremental_ev: float
    eligibility: str
    selection_rank: int | None
    skip_reason: str | None


@dataclass
class OptimizationPlan:
    """Complete optimization plan for a simulated day."""

    run_id: str
    merchant_id: str
    simulated_day: int
    created_at: str

    daily_capacity: int
    selected_count: int

    expected_gross_recovery: float
    expected_net_recovery: float
    expected_incremental_recovery: float

    selected_actions: list[OpportunityDecision]
    skipped_actions: list[OpportunityDecision]


class ConstrainedRecoveryOptimizer:
    """
    Constrained recovery optimizer for RAY V1.

    Maximizes expected incremental recovery while respecting:
    - Daily capacity constraints
    - Eligibility constraints
    - Economic viability (positive incremental EV)
    """

    def __init__(
        self,
        prediction_provider: RecoveryProbabilityProvider,
        eligibility_provider: ActionEligibilityProvider,
        assumed_organic_recovery_rate: float = 0.04,
        intervention_cost: float = 0.0,
        friction_cost: float = 5.0,
        risk_penalty: float = 0.0,
    ):
        """
        Initialize optimizer.

        Args:
            prediction_provider: Probability prediction interface
            eligibility_provider: Eligibility determination interface
            assumed_organic_recovery_rate: Business assumption for do_nothing
            intervention_cost: Cost per payment link creation
            friction_cost: Customer friction cost per contact
            risk_penalty: Risk penalty per payment link
        """
        self.prediction_provider = prediction_provider
        self.eligibility_provider = eligibility_provider
        self.assumed_organic_recovery_rate = assumed_organic_recovery_rate
        self.intervention_cost = intervention_cost
        self.friction_cost = friction_cost
        self.risk_penalty = risk_penalty

    def optimize_daily_opportunities(
        self,
        opportunities: list[dict[str, Any]],
        merchant_id: str,
        simulated_day: int,
        max_actions_per_day: int = 10,
    ) -> OptimizationPlan:
        """
        Optimize opportunities for a single simulated day.

        Args:
            opportunities: List of opportunity dictionaries
            merchant_id: Merchant identifier
            simulated_day: Simulated day number
            max_actions_per_day: Daily capacity constraint

        Returns:
            OptimizationPlan with selected and skipped actions
        """
        run_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Calculate decisions for all opportunities
        decisions = []
        for opp in opportunities:
            decision = self._evaluate_opportunity(opp)
            decisions.append(decision)

        # Filter to eligible positive-EV opportunities
        eligible_positive = [
            d
            for d in decisions
            if d.eligibility == ActionEligibility.ELIGIBLE.value
            and d.incremental_ev > 0
            and d.skip_reason is None
        ]

        # Sort by incremental EV descending, with deterministic tie-breaking
        eligible_positive.sort(
            key=lambda d: self._get_sort_key(d, opportunities), reverse=True
        )

        # Allocate capacity
        selected = eligible_positive[:max_actions_per_day]
        capacity_exceeded = eligible_positive[max_actions_per_day:]

        # Assign selection ranks
        for rank, decision in enumerate(selected, start=1):
            decision.selection_rank = rank

        # Mark capacity-exceeded as skipped
        for decision in capacity_exceeded:
            decision.selected_action = ActionType.DO_NOTHING.value
            decision.skip_reason = SkipReason.CAPACITY_EXCEEDED.value

        # Collect all skipped decisions
        skipped = [
            d
            for d in decisions
            if d.selected_action == ActionType.DO_NOTHING.value
        ]

        # Calculate expected values
        expected_gross = sum(
            d.payment_link_ev + self.friction_cost + self.risk_penalty
            for d in selected
        )
        expected_net = sum(d.payment_link_ev for d in selected)
        expected_incremental = sum(d.incremental_ev for d in selected)

        return OptimizationPlan(
            run_id=run_id,
            merchant_id=merchant_id,
            simulated_day=simulated_day,
            created_at=created_at,
            daily_capacity=max_actions_per_day,
            selected_count=len(selected),
            expected_gross_recovery=expected_gross,
            expected_net_recovery=expected_net,
            expected_incremental_recovery=expected_incremental,
            selected_actions=selected,
            skipped_actions=skipped,
        )

    def _evaluate_opportunity(
        self, opportunity: dict[str, Any]
    ) -> OpportunityDecision:
        """
        Evaluate a single opportunity and calculate decision.

        Args:
            opportunity: Opportunity dictionary

        Returns:
            OpportunityDecision with economic values and action
        """
        opportunity_id = opportunity["opportunity_id"]
        amount = opportunity["amount"]

        # Get probability prediction
        try:
            payment_link_prob = self.prediction_provider.predict_payment_link_probability(
                opportunity
            )

            # Validate prediction
            if (
                payment_link_prob < 0
                or payment_link_prob > 1
                or payment_link_prob != payment_link_prob  # NaN check
            ):
                # Invalid prediction
                return self._create_invalid_decision(opportunity_id, amount)

        except Exception as e:
            # Prediction failed
            return self._create_invalid_decision(opportunity_id, amount)

        # Check eligibility
        eligibility = self.eligibility_provider.check_eligibility(
            opportunity, ActionType.CREATE_PAYMENT_LINK.value
        )

        # Calculate economic values
        payment_link_gross_ev = payment_link_prob * amount
        payment_link_net_ev = (
            payment_link_gross_ev
            - self.intervention_cost
            - self.friction_cost
            - self.risk_penalty
        )

        do_nothing_ev = self.assumed_organic_recovery_rate * amount

        incremental_ev = payment_link_net_ev - do_nothing_ev

        # Determine action
        if eligibility == ActionEligibility.INELIGIBLE:
            selected_action = ActionType.DO_NOTHING.value
            skip_reason = SkipReason.INELIGIBLE.value
        elif incremental_ev <= 0:
            selected_action = ActionType.DO_NOTHING.value
            skip_reason = SkipReason.NEGATIVE_INCREMENTAL_VALUE.value
        else:
            # Positive EV and eligible: candidate for selection
            selected_action = ActionType.CREATE_PAYMENT_LINK.value
            skip_reason = None

        return OpportunityDecision(
            opportunity_id=opportunity_id,
            selected_action=selected_action,
            payment_link_probability=payment_link_prob,
            assumed_organic_probability=self.assumed_organic_recovery_rate,
            payment_link_ev=payment_link_net_ev,
            do_nothing_ev=do_nothing_ev,
            incremental_ev=incremental_ev,
            eligibility=eligibility.value,
            selection_rank=None,
            skip_reason=skip_reason,
        )

    def _create_invalid_decision(
        self, opportunity_id: str, amount: float
    ) -> OpportunityDecision:
        """Create decision for invalid prediction."""
        do_nothing_ev = self.assumed_organic_recovery_rate * amount

        return OpportunityDecision(
            opportunity_id=opportunity_id,
            selected_action=ActionType.DO_NOTHING.value,
            payment_link_probability=0.0,
            assumed_organic_probability=self.assumed_organic_recovery_rate,
            payment_link_ev=0.0,
            do_nothing_ev=do_nothing_ev,
            incremental_ev=-do_nothing_ev,
            eligibility=ActionEligibility.ELIGIBLE.value,
            selection_rank=None,
            skip_reason=SkipReason.INVALID_PREDICTION.value,
        )

    def _get_sort_key(
        self, decision: OpportunityDecision, opportunities: list[dict[str, Any]]
    ) -> tuple:
        """
        Get deterministic sort key for tie-breaking.

        Tie-breaking order:
        1. Higher incremental_EV
        2. Higher recoverable_amount
        3. Higher payment_link_probability
        4. Earlier occurred_at
        5. opportunity_id ascending

        Returns:
            Tuple for sorting (higher values first)
        """
        # Find opportunity for additional fields
        opp = next(
            (o for o in opportunities if o["opportunity_id"] == decision.opportunity_id),
            None,
        )

        if opp is None:
            # Fallback if opportunity not found
            return (
                decision.incremental_ev,
                0.0,
                decision.payment_link_probability,
                "",
                decision.opportunity_id,
            )

        amount = opp.get("amount", 0.0)
        occurred_at = opp.get("created_at", "")

        # Return tuple for sorting (all ascending except opportunity_id at end)
        # Note: occurred_at earlier = smaller string (reverse for "earlier first")
        return (
            decision.incremental_ev,
            amount,
            decision.payment_link_probability,
            occurred_at,  # Earlier timestamp = smaller value, sorts first when reversed
            decision.opportunity_id,  # Ascending for final tie-break
        )
