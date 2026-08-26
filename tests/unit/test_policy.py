"""
Tests for deterministic policy engine.

Verifies:
- Rule evaluation order
- Block reasons
- Deterministic behavior
- Capacity enforcement
- Contact tracking
- Do-not-contact enforcement
- Amount limits
- Idempotency
- Adversarial scenarios
"""

import pytest
from decimal import Decimal

from policy.engine import DeterministicPolicyEngine
from policy.types import (
    PolicyDecisionType,
    BlockReason,
    ExecutionState,
    MerchantPolicy,
)
from optimizer.core import (
    OptimizationPlan,
    OpportunityDecision,
    ActionType,
)


@pytest.fixture
def policy_engine():
    """Create policy engine with v1.0.0 version."""
    return DeterministicPolicyEngine(policy_version="1.0.0")


@pytest.fixture
def merchant_policy():
    """Create default merchant policy."""
    return MerchantPolicy(
        merchant_id="test_merchant",
        max_actions_per_day=10,
        max_contacts_per_customer_per_day=1,
        autonomous_amount_limit=25000.0,
        policy_version="1.0.0",
        do_not_contact_list=set(),
    )


@pytest.fixture
def empty_execution_state():
    """Create empty execution state."""
    return ExecutionState.create_empty()


def create_opportunity(
    opp_id: str,
    customer_id: str,
    amount: float,
) -> dict:
    """Helper to create test opportunity."""
    return {
        "opportunity_id": opp_id,
        "customer_id": customer_id,
        "amount": amount,
        "failure_class": "soft_decline",
        "created_at": "2026-01-01T00:00:00Z",
    }


class TestBasicRules:
    """Test individual policy rules."""

    def test_valid_action_allow(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 1: Valid payment link with all checks passing."""
        opportunity = create_opportunity("opp_001", "cust_001", 10000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.ALLOW.value
        assert decision.primary_reason is None
        assert decision.opportunity_id == "opp_001"
        assert decision.action_type == ActionType.CREATE_PAYMENT_LINK.value
        assert decision.policy_version == "1.0.0"

        # All rules should pass
        assert all(rule.passed for rule in decision.all_rule_results)

    def test_do_not_contact_block(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 2: Do-not-contact blocks action."""
        # Add customer to DNC list
        merchant_policy.do_not_contact_list.add("cust_dnc")

        opportunity = create_opportunity("opp_002", "cust_dnc", 10000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.DO_NOT_CONTACT.value
        assert decision.opportunity_id == "opp_002"

    def test_amount_limit_exceeded_block(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 3: Amount > ₹25,000 blocks action."""
        opportunity = create_opportunity("opp_003", "cust_003", 30000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert (
            decision.primary_reason
            == BlockReason.AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED.value
        )
        assert decision.opportunity_id == "opp_003"

    def test_max_contacts_exceeded_block(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 4: Customer already contacted today blocks action."""
        # Record existing contact for customer
        empty_execution_state.customer_contact_counts[
            ("test_merchant", "cust_004", 1)
        ] = 1

        opportunity = create_opportunity("opp_004", "cust_004", 10000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.MAX_CONTACTS_EXCEEDED.value
        assert decision.opportunity_id == "opp_004"

    def test_opportunity_not_actionable_block(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 5: Already recovered opportunity blocks action."""
        # Mark opportunity as recovered
        empty_execution_state.opportunity_states["opp_005"] = "recovered"

        opportunity = create_opportunity("opp_005", "cust_005", 10000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert (
            decision.primary_reason
            == BlockReason.OPPORTUNITY_NOT_ACTIONABLE.value
        )
        assert decision.opportunity_id == "opp_005"

    def test_duplicate_action_block(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 6: Already executed action blocks (idempotency)."""
        # Record action as already executed
        empty_execution_state.executed_actions.add(
            ("test_merchant", "opp_006", ActionType.CREATE_PAYMENT_LINK.value)
        )

        opportunity = create_opportunity("opp_006", "cust_006", 10000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.DUPLICATE_ACTION.value
        assert decision.opportunity_id == "opp_006"

    def test_invalid_action_block(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 7: Invalid action type blocks."""
        opportunity = create_opportunity("opp_007", "cust_007", 10000.0)

        # Try to execute do_nothing (not a valid executable action)
        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.DO_NOTHING.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.INVALID_ACTION.value
        assert decision.opportunity_id == "opp_007"


class TestCapacityEnforcement:
    """Test capacity constraint enforcement."""

    def test_capacity_exactly_at_limit(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 8: Capacity exactly at limit allows final eligible action."""
        # Create 10 opportunities (exactly at capacity)
        opportunities = [
            create_opportunity(f"opp_{i:03d}", f"cust_{i:03d}", 10000.0)
            for i in range(10)
        ]

        # Create optimization plan with 10 selected actions
        selected_actions = [
            OpportunityDecision(
                opportunity_id=f"opp_{i:03d}",
                selected_action=ActionType.CREATE_PAYMENT_LINK.value,
                payment_link_probability=0.5,
                assumed_organic_probability=0.04,
                payment_link_ev=5000.0,
                do_nothing_ev=400.0,
                incremental_ev=4600.0,
                eligibility="ELIGIBLE",
                selection_rank=i + 1,
                skip_reason=None,
            )
            for i in range(10)
        ]

        plan = OptimizationPlan(
            run_id="test_run",
            merchant_id="test_merchant",
            simulated_day=1,
            created_at="2026-01-01T00:00:00Z",
            daily_capacity=10,
            selected_count=10,
            expected_gross_recovery=50000.0,
            expected_net_recovery=49950.0,
            expected_incremental_recovery=46000.0,
            selected_actions=selected_actions,
            skipped_actions=[],
        )

        result = policy_engine.evaluate_optimization_plan(
            optimization_plan=plan,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            opportunities=opportunities,
        )

        # All 10 should be allowed (exactly at capacity)
        assert result.total_allowed == 10
        assert result.total_blocked == 0
        assert len(result.allowed_actions) == 10

    def test_capacity_exceeded_blocks_excess(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 9: Capacity exceeded blocks excess actions."""
        # Create 15 opportunities (exceeds capacity of 10)
        opportunities = [
            create_opportunity(f"opp_{i:03d}", f"cust_{i:03d}", 10000.0)
            for i in range(15)
        ]

        # Create malformed plan with 15 selected actions (should never happen from optimizer)
        selected_actions = [
            OpportunityDecision(
                opportunity_id=f"opp_{i:03d}",
                selected_action=ActionType.CREATE_PAYMENT_LINK.value,
                payment_link_probability=0.5,
                assumed_organic_probability=0.04,
                payment_link_ev=5000.0,
                do_nothing_ev=400.0,
                incremental_ev=4600.0,
                eligibility="ELIGIBLE",
                selection_rank=i + 1,
                skip_reason=None,
            )
            for i in range(15)
        ]

        plan = OptimizationPlan(
            run_id="test_run",
            merchant_id="test_merchant",
            simulated_day=1,
            created_at="2026-01-01T00:00:00Z",
            daily_capacity=10,
            selected_count=15,
            expected_gross_recovery=75000.0,
            expected_net_recovery=74925.0,
            expected_incremental_recovery=69000.0,
            selected_actions=selected_actions,
            skipped_actions=[],
        )

        result = policy_engine.evaluate_optimization_plan(
            optimization_plan=plan,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            opportunities=opportunities,
        )

        # Only first 10 allowed, remaining 5 blocked
        assert result.total_allowed == 10
        assert result.total_blocked == 5
        assert (
            result.block_reasons[BlockReason.DAILY_CAPACITY_EXCEEDED.value] == 5
        )


class TestContactTracking:
    """Test customer contact tracking."""

    def test_two_actions_same_customer_blocks_second(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 10: Two actions for same customer blocks second."""
        # Create 2 opportunities for same customer
        opportunities = [
            create_opportunity("opp_001", "cust_same", 10000.0),
            create_opportunity("opp_002", "cust_same", 10000.0),
        ]

        selected_actions = [
            OpportunityDecision(
                opportunity_id="opp_001",
                selected_action=ActionType.CREATE_PAYMENT_LINK.value,
                payment_link_probability=0.5,
                assumed_organic_probability=0.04,
                payment_link_ev=5000.0,
                do_nothing_ev=400.0,
                incremental_ev=4600.0,
                eligibility="ELIGIBLE",
                selection_rank=1,
                skip_reason=None,
            ),
            OpportunityDecision(
                opportunity_id="opp_002",
                selected_action=ActionType.CREATE_PAYMENT_LINK.value,
                payment_link_probability=0.5,
                assumed_organic_probability=0.04,
                payment_link_ev=5000.0,
                do_nothing_ev=400.0,
                incremental_ev=4600.0,
                eligibility="ELIGIBLE",
                selection_rank=2,
                skip_reason=None,
            ),
        ]

        plan = OptimizationPlan(
            run_id="test_run",
            merchant_id="test_merchant",
            simulated_day=1,
            created_at="2026-01-01T00:00:00Z",
            daily_capacity=10,
            selected_count=2,
            expected_gross_recovery=10000.0,
            expected_net_recovery=9990.0,
            expected_incremental_recovery=9200.0,
            selected_actions=selected_actions,
            skipped_actions=[],
        )

        result = policy_engine.evaluate_optimization_plan(
            optimization_plan=plan,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            opportunities=opportunities,
        )

        # Only first action allowed, second blocked
        assert result.total_allowed == 1
        assert result.total_blocked == 1
        assert result.allowed_actions[0].opportunity_id == "opp_001"
        assert result.blocked_actions[0].opportunity_id == "opp_002"
        assert (
            result.blocked_actions[0].primary_reason
            == BlockReason.MAX_CONTACTS_EXCEEDED.value
        )


class TestDeterminism:
    """Test deterministic behavior."""

    def test_same_input_same_output(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 11: Same input produces identical output."""
        opportunity = create_opportunity("opp_det", "cust_det", 10000.0)

        # Evaluate twice
        decision1 = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        decision2 = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        # Decisions should be identical (except timestamp)
        assert decision1.decision == decision2.decision
        assert decision1.opportunity_id == decision2.opportunity_id
        assert decision1.action_type == decision2.action_type
        assert decision1.primary_reason == decision2.primary_reason
        assert decision1.policy_version == decision2.policy_version

        # Rule results should be identical
        assert len(decision1.all_rule_results) == len(
            decision2.all_rule_results
        )
        for rule1, rule2 in zip(
            decision1.all_rule_results, decision2.all_rule_results
        ):
            assert rule1.rule_id == rule2.rule_id
            assert rule1.passed == rule2.passed
            assert rule1.reason == rule2.reason


class TestObservableFeaturesOnly:
    """Test that policy works with observable data only."""

    def test_policy_without_hidden_simulator_data(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test 12: Policy works using observable features only."""
        # Create opportunity with ONLY observable features
        # (no true_payment_link_probability, no hidden traits)
        opportunity = {
            "opportunity_id": "opp_obs",
            "customer_id": "cust_obs",
            "amount": 15000.0,
            "failure_class": "soft_decline",
            "created_at": "2026-01-01T00:00:00Z",
            # NO hidden simulator data
        }

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        # Should work without hidden data
        assert decision.decision == PolicyDecisionType.ALLOW.value
        assert decision.primary_reason is None


class TestRuleOrdering:
    """Test that rules are evaluated in correct order."""

    def test_rule_ordering_invalid_action_first(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test that invalid action is caught first."""
        # Create opportunity that would fail multiple rules
        merchant_policy.do_not_contact_list.add("cust_multi")
        empty_execution_state.opportunity_states["opp_multi"] = "recovered"

        opportunity = create_opportunity("opp_multi", "cust_multi", 30000.0)

        # But use invalid action - this should be caught FIRST
        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action="invalid_action_type",
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        # Invalid action should be primary reason (first rule)
        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.INVALID_ACTION.value

    def test_rule_ordering_do_not_contact_before_amount(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test that do-not-contact is checked before amount limit."""
        # Create opportunity that violates both DNC and amount limit
        merchant_policy.do_not_contact_list.add("cust_both")

        opportunity = create_opportunity("opp_both", "cust_both", 30000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        # DNC should be primary reason (comes before amount limit in order)
        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.DO_NOT_CONTACT.value


class TestAdversarialScenarios:
    """Test adversarial attempts to bypass policy."""

    def test_adversarial_amount_just_over_limit(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test amount of ₹25,001 (just over limit) is blocked."""
        opportunity = create_opportunity("opp_adv1", "cust_adv1", 25001.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert (
            decision.primary_reason
            == BlockReason.AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED.value
        )

    def test_adversarial_amount_exactly_at_limit(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test amount of exactly ₹25,000 (at limit) is allowed."""
        opportunity = create_opportunity("opp_adv2", "cust_adv2", 25000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.ALLOW.value
        assert decision.primary_reason is None

    def test_adversarial_malformed_opportunity(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test malformed opportunity (missing fields) is handled."""
        # Malformed opportunity with missing amount
        opportunity = {
            "opportunity_id": "opp_malformed",
            "customer_id": "cust_malformed",
            # Missing amount field
        }

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        # Should handle gracefully (amount defaults to 0.0, which is <= limit)
        assert decision.decision == PolicyDecisionType.ALLOW.value

    def test_adversarial_unknown_action_string(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test unknown action string is blocked."""
        opportunity = create_opportunity("opp_adv4", "cust_adv4", 10000.0)

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action="send_email",  # Unknown action
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert decision.primary_reason == BlockReason.INVALID_ACTION.value

    def test_adversarial_optimizer_exceeds_capacity(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test that policy defensively blocks if optimizer violates capacity."""
        # Create 20 opportunities but only 10 capacity
        opportunities = [
            create_opportunity(f"opp_{i:03d}", f"cust_{i:03d}", 10000.0)
            for i in range(20)
        ]

        # Malformed plan with 20 selected (optimizer bug scenario)
        selected_actions = [
            OpportunityDecision(
                opportunity_id=f"opp_{i:03d}",
                selected_action=ActionType.CREATE_PAYMENT_LINK.value,
                payment_link_probability=0.5,
                assumed_organic_probability=0.04,
                payment_link_ev=5000.0,
                do_nothing_ev=400.0,
                incremental_ev=4600.0,
                eligibility="ELIGIBLE",
                selection_rank=i + 1,
                skip_reason=None,
            )
            for i in range(20)
        ]

        plan = OptimizationPlan(
            run_id="test_run",
            merchant_id="test_merchant",
            simulated_day=1,
            created_at="2026-01-01T00:00:00Z",
            daily_capacity=10,
            selected_count=20,
            expected_gross_recovery=100000.0,
            expected_net_recovery=99900.0,
            expected_incremental_recovery=92000.0,
            selected_actions=selected_actions,
            skipped_actions=[],
        )

        result = policy_engine.evaluate_optimization_plan(
            optimization_plan=plan,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            opportunities=opportunities,
        )

        # Policy should defensively enforce capacity
        assert result.total_allowed == 10
        assert result.total_blocked == 10
        assert (
            result.block_reasons[BlockReason.DAILY_CAPACITY_EXCEEDED.value]
            == 10
        )

    def test_adversarial_multiple_violations(
        self, policy_engine, merchant_policy, empty_execution_state
    ):
        """Test opportunity violating multiple rules returns first violation."""
        # Setup multiple violations
        merchant_policy.do_not_contact_list.add("cust_multi_adv")
        empty_execution_state.opportunity_states["opp_multi_adv"] = "closed"
        empty_execution_state.executed_actions.add(
            (
                "test_merchant",
                "opp_multi_adv",
                ActionType.CREATE_PAYMENT_LINK.value,
            )
        )

        opportunity = create_opportunity(
            "opp_multi_adv", "cust_multi_adv", 30000.0
        )

        decision = policy_engine.evaluate_action(
            opportunity=opportunity,
            action=ActionType.CREATE_PAYMENT_LINK.value,
            merchant_policy=merchant_policy,
            execution_state=empty_execution_state,
            simulated_day=1,
        )

        # Should return FIRST violation in order (opportunity not actionable)
        assert decision.decision == PolicyDecisionType.BLOCK.value
        assert (
            decision.primary_reason
            == BlockReason.OPPORTUNITY_NOT_ACTIONABLE.value
        )
