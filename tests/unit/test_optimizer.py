"""
Tests for constrained recovery optimizer.

Verifies:
- Capacity constraints
- Economic calculations
- Tie-breaking
- Eligibility handling
- Invalid prediction handling
- Deterministic output
"""

import pytest
from optimizer.core import (
    ConstrainedRecoveryOptimizer,
    ActionType,
    SkipReason,
)
from optimizer.dev_providers import (
    DevelopmentRecoveryProbabilityProvider,
    DevelopmentEligibilityProvider,
)
from optimizer.interfaces import ActionEligibility


@pytest.fixture
def optimizer():
    """Create optimizer with development fixtures."""
    prediction_provider = DevelopmentRecoveryProbabilityProvider()
    eligibility_provider = DevelopmentEligibilityProvider()

    return ConstrainedRecoveryOptimizer(
        prediction_provider=prediction_provider,
        eligibility_provider=eligibility_provider,
        assumed_organic_recovery_rate=0.04,
        intervention_cost=0.0,
        friction_cost=5.0,
        risk_penalty=0.0,
    )


def create_opportunity(
    opp_id: str,
    amount: float,
    failure_class: str = "soft_decline",
    recovery_rate: float = 0.3,
    success_rate: float = 0.6,
    avg_amount: float = None,
) -> dict:
    """Helper to create test opportunity."""
    if avg_amount is None:
        avg_amount = amount

    return {
        "opportunity_id": opp_id,
        "amount": amount,
        "failure_class": failure_class,
        "historical_recovery_rate": recovery_rate,
        "historical_success_rate": success_rate,
        "avg_payment_amount": avg_amount,
        "created_at": "2026-01-01T00:00:00Z",
    }


class TestCapacityConstraints:
    """Test capacity constraint behavior."""

    def test_plenty_of_capacity(self, optimizer):
        """Case 1: Fewer opportunities than capacity."""
        opportunities = [
            create_opportunity(f"opp_{i:03d}", 10000.0, "soft_decline")
            for i in range(5)
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        assert plan.selected_count == 5  # All 5 selected
        assert plan.daily_capacity == 10
        assert len(plan.selected_actions) == 5
        assert all(
            d.selected_action == ActionType.CREATE_PAYMENT_LINK.value
            for d in plan.selected_actions
        )

    def test_capacity_constrained(self, optimizer):
        """Case 2: More opportunities than capacity."""
        opportunities = [
            create_opportunity(f"opp_{i:03d}", 10000.0, "soft_decline")
            for i in range(20)
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        assert plan.selected_count == 10  # Exactly capacity
        assert plan.daily_capacity == 10
        assert len(plan.selected_actions) == 10

        # Check capacity exceeded opportunities are skipped
        capacity_exceeded = [
            d
            for d in plan.skipped_actions
            if d.skip_reason == SkipReason.CAPACITY_EXCEEDED.value
        ]
        assert len(capacity_exceeded) == 10  # 20 - 10 = 10 exceeded

    def test_capacity_reset_across_days(self, optimizer):
        """Case 8: Capacity resets each day."""
        opportunities_day1 = [
            create_opportunity(f"opp_d1_{i:03d}", 10000.0)
            for i in range(5)
        ]
        opportunities_day2 = [
            create_opportunity(f"opp_d2_{i:03d}", 10000.0)
            for i in range(5)
        ]

        plan_day1 = optimizer.optimize_daily_opportunities(
            opportunities=opportunities_day1,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        plan_day2 = optimizer.optimize_daily_opportunities(
            opportunities=opportunities_day2,
            merchant_id="test_merchant",
            simulated_day=2,
            max_actions_per_day=10,
        )

        # Both days select all opportunities (independent)
        assert plan_day1.selected_count == 5
        assert plan_day2.selected_count == 5
        assert plan_day1.simulated_day == 1
        assert plan_day2.simulated_day == 2


class TestEconomicCalculations:
    """Test economic value calculations."""

    def test_negative_incremental_value(self, optimizer):
        """Case 3: Payment link EV < do_nothing EV."""
        # Hard decline with low recovery history + tiny amount
        # = low probability (0.15), friction cost (5) dominates
        # payment_link_ev = 0.15 * 30 - 5 = 4.5 - 5 = -0.5
        # do_nothing_ev = 0.04 * 30 = 1.2
        # incremental = -0.5 - 1.2 = -1.7 (negative!)
        opportunities = [
            create_opportunity(
                "opp_001",
                amount=30.0,  # Tiny amount - friction cost dominates
                failure_class="hard_decline",
                recovery_rate=0.0,
                success_rate=0.0,  # Worst case
            )
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # Should be skipped due to negative incremental value
        assert plan.selected_count == 0
        assert len(plan.skipped_actions) == 1

        skipped = plan.skipped_actions[0]
        assert skipped.skip_reason == SkipReason.NEGATIVE_INCREMENTAL_VALUE.value
        assert skipped.selected_action == ActionType.DO_NOTHING.value
        assert skipped.incremental_ev <= 0

    def test_exact_economic_calculation(self, optimizer):
        """Verify exact economic formula."""
        # Create opportunity with known values
        opportunity = {
            "opportunity_id": "opp_exact",
            "amount": 20000.0,
            "failure_class": "soft_decline",
            "historical_recovery_rate": 0.5,  # Will boost probability
            "historical_success_rate": 0.8,  # Will boost probability
            "avg_payment_amount": 20000.0,
            "created_at": "2026-01-01T00:00:00Z",
        }

        # Calculate expected probability using dev formula
        # Base (soft_decline): 0.45
        # Recovery adjustment: 0.5 * 0.3 = 0.15
        # Success adjustment: 0.8 * 0.2 = 0.16
        # Value adjustment: 0 (amount = avg)
        # Expected: 0.45 + 0.15 + 0.16 = 0.76

        plan = optimizer.optimize_daily_opportunities(
            opportunities=[opportunity],
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        decision = plan.selected_actions[0]

        # Verify calculations
        assert decision.payment_link_probability == 0.76
        assert decision.assumed_organic_probability == 0.04

        # Gross EV = 0.76 * 20000 = 15200
        expected_gross_ev = 0.76 * 20000
        assert abs(decision.payment_link_ev - (expected_gross_ev - 5.0)) < 0.01

        # Do nothing EV = 0.04 * 20000 = 800
        expected_do_nothing_ev = 0.04 * 20000
        assert decision.do_nothing_ev == expected_do_nothing_ev

        # Incremental = (15200 - 5) - 800 = 14395
        expected_incremental = (expected_gross_ev - 5.0) - expected_do_nothing_ev
        assert abs(decision.incremental_ev - expected_incremental) < 0.01

    def test_mixed_opportunities(self, optimizer):
        """Case 4: Some positive EV, some negative EV."""
        opportunities = [
            # High EV (soft decline, good history, high amount)
            create_opportunity(
                "opp_pos_1", 10000.0, "soft_decline", 0.5, 0.8
            ),
            # Negative EV (hard decline, poor history, tiny amount)
            create_opportunity(
                "opp_neg_1", 30.0, "hard_decline", 0.0, 0.0
            ),
            # High EV
            create_opportunity(
                "opp_pos_2", 10000.0, "soft_decline", 0.4, 0.7
            ),
            # Negative EV (tiny amount, friction dominates)
            create_opportunity(
                "opp_neg_2", 25.0, "hard_decline", 0.0, 0.0
            ),
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # Should select only positive EV opportunities
        assert plan.selected_count == 2
        selected_ids = {d.opportunity_id for d in plan.selected_actions}
        assert selected_ids == {"opp_pos_1", "opp_pos_2"}

        # Negative EV opportunities should be skipped
        negative_skipped = [
            d
            for d in plan.skipped_actions
            if d.skip_reason == SkipReason.NEGATIVE_INCREMENTAL_VALUE.value
        ]
        assert len(negative_skipped) == 2


class TestEligibilityHandling:
    """Test eligibility constraint handling."""

    def test_ineligible_opportunity(self, optimizer):
        """Case 5: Policy marks opportunity as ineligible."""
        # Note: Dev eligibility provider always returns ELIGIBLE
        # We need to test the logic pathway, not the dev provider behavior

        # For this test, we verify the optimizer respects eligibility
        # by checking that ineligible opportunities get do_nothing

        # Create custom eligibility provider for this test
        class AlwaysIneligibleProvider:
            def check_eligibility(self, opportunity, action):
                if action == "create_payment_link":
                    return ActionEligibility.INELIGIBLE
                return ActionEligibility.ELIGIBLE

        test_optimizer = ConstrainedRecoveryOptimizer(
            prediction_provider=DevelopmentRecoveryProbabilityProvider(),
            eligibility_provider=AlwaysIneligibleProvider(),
            assumed_organic_recovery_rate=0.04,
        )

        opportunities = [
            create_opportunity("opp_001", 10000.0, "soft_decline")
        ]

        plan = test_optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # Should be skipped due to ineligibility
        assert plan.selected_count == 0
        assert len(plan.skipped_actions) == 1

        skipped = plan.skipped_actions[0]
        assert skipped.skip_reason == SkipReason.INELIGIBLE.value
        assert skipped.selected_action == ActionType.DO_NOTHING.value


class TestInvalidPredictions:
    """Test invalid prediction handling."""

    def test_nan_probability(self, optimizer):
        """Case 6: Prediction returns NaN."""

        class NaNProvider:
            def predict_payment_link_probability(self, opportunity):
                return float("nan")

        test_optimizer = ConstrainedRecoveryOptimizer(
            prediction_provider=NaNProvider(),
            eligibility_provider=DevelopmentEligibilityProvider(),
            assumed_organic_recovery_rate=0.04,
        )

        opportunities = [
            create_opportunity("opp_001", 10000.0)
        ]

        plan = test_optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # Should be skipped with INVALID_PREDICTION
        assert plan.selected_count == 0
        decision = plan.skipped_actions[0]
        assert decision.skip_reason == SkipReason.INVALID_PREDICTION.value

    def test_negative_probability(self, optimizer):
        """Invalid prediction: negative probability."""

        class NegativeProvider:
            def predict_payment_link_probability(self, opportunity):
                return -0.5

        test_optimizer = ConstrainedRecoveryOptimizer(
            prediction_provider=NegativeProvider(),
            eligibility_provider=DevelopmentEligibilityProvider(),
            assumed_organic_recovery_rate=0.04,
        )

        opportunities = [create_opportunity("opp_001", 10000.0)]

        plan = test_optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        assert plan.selected_count == 0
        assert plan.skipped_actions[0].skip_reason == SkipReason.INVALID_PREDICTION.value

    def test_probability_above_one(self, optimizer):
        """Invalid prediction: probability > 1.0."""

        class AboveOneProvider:
            def predict_payment_link_probability(self, opportunity):
                return 1.5

        test_optimizer = ConstrainedRecoveryOptimizer(
            prediction_provider=AboveOneProvider(),
            eligibility_provider=DevelopmentEligibilityProvider(),
            assumed_organic_recovery_rate=0.04,
        )

        opportunities = [create_opportunity("opp_001", 10000.0)]

        plan = test_optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        assert plan.selected_count == 0
        assert plan.skipped_actions[0].skip_reason == SkipReason.INVALID_PREDICTION.value


class TestTieBreaking:
    """Test deterministic tie-breaking."""

    def test_tie_breaking_by_amount(self, optimizer):
        """Case 7: Equal EV, break tie by amount."""
        # Create opportunities with similar characteristics but different amounts
        opportunities = [
            create_opportunity("opp_001", 5000.0, "soft_decline", 0.3, 0.6),
            create_opportunity("opp_002", 10000.0, "soft_decline", 0.3, 0.6),
            create_opportunity("opp_003", 7500.0, "soft_decline", 0.3, 0.6),
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=2,
        )

        # Higher amount should be selected first (after EV)
        assert plan.selected_count == 2
        assert plan.selected_actions[0].opportunity_id == "opp_002"  # 10000
        assert plan.selected_actions[1].opportunity_id == "opp_003"  # 7500

    def test_deterministic_output(self, optimizer):
        """Verify same inputs produce same outputs."""
        opportunities = [
            create_opportunity(f"opp_{i:03d}", 10000.0)
            for i in range(15)
        ]

        plan1 = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        plan2 = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # run_id will differ, but selections should be identical
        selected_ids1 = [d.opportunity_id for d in plan1.selected_actions]
        selected_ids2 = [d.opportunity_id for d in plan2.selected_actions]

        assert selected_ids1 == selected_ids2
        assert plan1.selected_count == plan2.selected_count
        assert plan1.expected_incremental_recovery == plan2.expected_incremental_recovery


class TestRankingBehavior:
    """Test ranking and selection behavior."""

    def test_selection_ranks_assigned(self, optimizer):
        """Verify selection ranks are assigned correctly."""
        opportunities = [
            create_opportunity(f"opp_{i:03d}", 10000.0 - i*100)
            for i in range(5)
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # All selected should have ranks
        for i, decision in enumerate(plan.selected_actions, start=1):
            assert decision.selection_rank == i

        # Skipped should have no rank
        for decision in plan.skipped_actions:
            assert decision.selection_rank is None

    def test_highest_ev_selected_first(self, optimizer):
        """Verify highest incremental EV selected first."""
        opportunities = [
            # Low value, low probability
            create_opportunity("opp_low", 1000.0, "hard_decline", 0.0, 0.2),
            # Medium value, medium probability
            create_opportunity("opp_med", 5000.0, "soft_decline", 0.2, 0.5),
            # High value, high probability
            create_opportunity("opp_high", 10000.0, "soft_decline", 0.5, 0.8),
        ]

        plan = optimizer.optimize_daily_opportunities(
            opportunities=opportunities,
            merchant_id="test_merchant",
            simulated_day=1,
            max_actions_per_day=10,
        )

        # Highest EV should be ranked first
        assert plan.selected_actions[0].opportunity_id == "opp_high"
        assert plan.selected_actions[0].selection_rank == 1

        # Verify descending EV order
        evs = [d.incremental_ev for d in plan.selected_actions]
        assert evs == sorted(evs, reverse=True)
