"""
RAY V1 Deterministic Policy Engine.

The policy engine is the authorization layer that sits AFTER optimization
and BEFORE execution. It answers: "Is this action permitted?"

Key principles:
- Deterministic (same input → same output)
- No re-optimization
- No LLM calls
- No ML predictions
- Pure business logic
"""

from datetime import datetime, timezone
from typing import Any

from policy.types import (
    PolicyDecision,
    PolicyDecisionType,
    BlockReason,
    RuleId,
    RuleResult,
    PolicyEvaluationResult,
    ExecutionState,
    MerchantPolicy,
)
from optimizer.core import OptimizationPlan, OpportunityDecision, ActionType


class DeterministicPolicyEngine:
    """
    Deterministic policy engine for RAY V1.

    Evaluates whether optimizer-selected actions are permitted under
    merchant policy constraints.

    Rules evaluated in order:
    1. VALID_ACTION_TYPE
    2. OPPORTUNITY_ACTIONABLE
    3. DO_NOT_CONTACT_CHECK
    4. DUPLICATE_ACTION_CHECK
    5. AUTONOMOUS_AMOUNT_LIMIT_CHECK
    6. MAX_CONTACTS_CHECK
    7. DAILY_CAPACITY_CHECK
    """

    def __init__(self, policy_version: str = "1.0.0"):
        """
        Initialize policy engine.

        Args:
            policy_version: Policy version identifier
        """
        self.policy_version = policy_version

    def evaluate_action(
        self,
        opportunity: dict[str, Any],
        action: str,
        merchant_policy: MerchantPolicy,
        execution_state: ExecutionState,
        simulated_day: int,
    ) -> PolicyDecision:
        """
        Evaluate whether a single action is permitted.

        Args:
            opportunity: Opportunity data
            action: Action to evaluate (create_payment_link or do_nothing)
            merchant_policy: Merchant policy configuration
            execution_state: Execution and idempotency state
            simulated_day: Current simulated day

        Returns:
            PolicyDecision with ALLOW or BLOCK
        """
        opportunity_id = opportunity["opportunity_id"]
        evaluated_at = datetime.now(timezone.utc).isoformat()

        # Evaluate all rules in order
        rule_results = []

        # Rule 1: Valid action type
        rule1 = self._check_valid_action_type(action)
        rule_results.append(rule1)
        if not rule1.passed:
            return self._create_decision(
                PolicyDecisionType.BLOCK,
                opportunity_id,
                action,
                evaluated_at,
                BlockReason.INVALID_ACTION,
                rule_results,
            )

        # Rule 2: Opportunity actionable
        rule2 = self._check_opportunity_actionable(
            opportunity_id, execution_state
        )
        rule_results.append(rule2)
        if not rule2.passed:
            return self._create_decision(
                PolicyDecisionType.BLOCK,
                opportunity_id,
                action,
                evaluated_at,
                BlockReason.OPPORTUNITY_NOT_ACTIONABLE,
                rule_results,
            )

        # Rule 3: Do-not-contact
        customer_id = opportunity.get("customer_id")
        rule3 = self._check_do_not_contact(customer_id, merchant_policy)
        rule_results.append(rule3)
        if not rule3.passed:
            return self._create_decision(
                PolicyDecisionType.BLOCK,
                opportunity_id,
                action,
                evaluated_at,
                BlockReason.DO_NOT_CONTACT,
                rule_results,
            )

        # Rule 4: Duplicate action
        rule4 = self._check_duplicate_action(
            merchant_policy.merchant_id,
            opportunity_id,
            action,
            execution_state,
        )
        rule_results.append(rule4)
        if not rule4.passed:
            return self._create_decision(
                PolicyDecisionType.BLOCK,
                opportunity_id,
                action,
                evaluated_at,
                BlockReason.DUPLICATE_ACTION,
                rule_results,
            )

        # Rule 5: Autonomous amount limit
        amount = opportunity.get("amount", 0.0)
        rule5 = self._check_autonomous_amount_limit(
            amount, merchant_policy.autonomous_amount_limit
        )
        rule_results.append(rule5)
        if not rule5.passed:
            return self._create_decision(
                PolicyDecisionType.BLOCK,
                opportunity_id,
                action,
                evaluated_at,
                BlockReason.AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED,
                rule_results,
            )

        # Rule 6: Max contacts per customer
        rule6 = self._check_max_contacts(
            merchant_policy.merchant_id,
            customer_id,
            simulated_day,
            merchant_policy.max_contacts_per_customer_per_day,
            execution_state,
        )
        rule_results.append(rule6)
        if not rule6.passed:
            return self._create_decision(
                PolicyDecisionType.BLOCK,
                opportunity_id,
                action,
                evaluated_at,
                BlockReason.MAX_CONTACTS_EXCEEDED,
                rule_results,
            )

        # Rule 7: Daily capacity (checked at plan level, always passes here)
        rule7 = RuleResult(
            rule_id=RuleId.DAILY_CAPACITY_CHECK.value,
            passed=True,
            reason=None,
            observed_value=None,
            configured_value=merchant_policy.max_actions_per_day,
        )
        rule_results.append(rule7)

        # All rules passed
        return self._create_decision(
            PolicyDecisionType.ALLOW,
            opportunity_id,
            action,
            evaluated_at,
            None,
            rule_results,
        )

    def evaluate_optimization_plan(
        self,
        optimization_plan: OptimizationPlan,
        merchant_policy: MerchantPolicy,
        execution_state: ExecutionState,
        opportunities: list[dict[str, Any]],
    ) -> PolicyEvaluationResult:
        """
        Evaluate an entire optimization plan.

        Args:
            optimization_plan: Optimizer output
            merchant_policy: Merchant policy configuration
            execution_state: Execution and idempotency state
            opportunities: Full opportunity data

        Returns:
            PolicyEvaluationResult with allowed and blocked actions
        """
        evaluated_at = datetime.now(timezone.utc).isoformat()

        # Create opportunity lookup
        opp_lookup = {
            opp["opportunity_id"]: opp for opp in opportunities
        }

        # Evaluate each selected action
        allowed_actions = []
        blocked_actions = []
        block_reasons = {}

        # Track capacity and contacts for this plan evaluation
        # (defensive checks even though optimizer already allocated)
        actions_allowed_count = 0
        customer_contacts_this_plan = {}

        for decision in optimization_plan.selected_actions:
            opportunity_id = decision.opportunity_id
            action_type = decision.selected_action

            # Get full opportunity data
            opportunity = opp_lookup.get(opportunity_id)
            if opportunity is None:
                # Shouldn't happen, but defensive
                blocked_actions.append(
                    self._create_decision(
                        PolicyDecisionType.BLOCK,
                        opportunity_id,
                        action_type,
                        evaluated_at,
                        BlockReason.OPPORTUNITY_NOT_ACTIONABLE,
                        [],
                    )
                )
                block_reasons[BlockReason.OPPORTUNITY_NOT_ACTIONABLE.value] = (
                    block_reasons.get(BlockReason.OPPORTUNITY_NOT_ACTIONABLE.value, 0) + 1
                )
                continue

            # Evaluate action
            policy_decision = self.evaluate_action(
                opportunity=opportunity,
                action=action_type,
                merchant_policy=merchant_policy,
                execution_state=execution_state,
                simulated_day=optimization_plan.simulated_day,
            )

            # Defensive capacity check (even though optimizer allocated)
            if policy_decision.decision == PolicyDecisionType.ALLOW.value:
                if actions_allowed_count >= merchant_policy.max_actions_per_day:
                    # Capacity exceeded - block this action
                    policy_decision = self._create_decision(
                        PolicyDecisionType.BLOCK,
                        opportunity_id,
                        action_type,
                        evaluated_at,
                        BlockReason.DAILY_CAPACITY_EXCEEDED,
                        policy_decision.all_rule_results,
                    )

            # Defensive max contacts check (within this plan)
            customer_id = opportunity.get("customer_id")
            if (
                policy_decision.decision == PolicyDecisionType.ALLOW.value
                and customer_id
            ):
                # Check if we've already allowed an action for this customer in this plan
                customer_key = (
                    merchant_policy.merchant_id,
                    customer_id,
                    optimization_plan.simulated_day,
                )

                existing_contacts = execution_state.customer_contact_counts.get(
                    customer_key, 0
                )
                new_contacts_this_plan = customer_contacts_this_plan.get(
                    customer_key, 0
                )

                if (
                    existing_contacts + new_contacts_this_plan
                    >= merchant_policy.max_contacts_per_customer_per_day
                ):
                    # Already contacted this customer (in state or earlier in plan)
                    policy_decision = self._create_decision(
                        PolicyDecisionType.BLOCK,
                        opportunity_id,
                        action_type,
                        evaluated_at,
                        BlockReason.MAX_CONTACTS_EXCEEDED,
                        policy_decision.all_rule_results,
                    )
                else:
                    # Track this contact
                    customer_contacts_this_plan[customer_key] = (
                        new_contacts_this_plan + 1
                    )

            # Collect results
            if policy_decision.decision == PolicyDecisionType.ALLOW.value:
                allowed_actions.append(policy_decision)
                actions_allowed_count += 1
            else:
                blocked_actions.append(policy_decision)
                if policy_decision.primary_reason:
                    block_reasons[policy_decision.primary_reason] = (
                        block_reasons.get(policy_decision.primary_reason, 0) + 1
                    )

        return PolicyEvaluationResult(
            plan_id=optimization_plan.run_id,
            policy_version=self.policy_version,
            evaluated_at=evaluated_at,
            allowed_actions=allowed_actions,
            blocked_actions=blocked_actions,
            total_evaluated=len(optimization_plan.selected_actions),
            total_allowed=len(allowed_actions),
            total_blocked=len(blocked_actions),
            block_reasons=block_reasons,
        )

    # === Rule Checks ===

    def _check_valid_action_type(self, action: str) -> RuleResult:
        """Check if action type is valid."""
        # Only create_payment_link requires execution authorization
        # do_nothing doesn't need policy authorization
        valid = action == ActionType.CREATE_PAYMENT_LINK.value

        return RuleResult(
            rule_id=RuleId.VALID_ACTION_TYPE.value,
            passed=valid,
            reason=None if valid else "Only create_payment_link is executable",
            observed_value=action,
            configured_value=ActionType.CREATE_PAYMENT_LINK.value,
        )

    def _check_opportunity_actionable(
        self, opportunity_id: str, execution_state: ExecutionState
    ) -> RuleResult:
        """Check if opportunity is still actionable."""
        # Get opportunity state
        state = execution_state.opportunity_states.get(opportunity_id)

        # States that indicate opportunity is NOT actionable
        non_actionable_states = {
            "recovered",
            "closed",
            "expired",
            "cancelled",
            "blocked",
            "safe_halt",
        }

        # If no state recorded, assume actionable (planning phase)
        # Valid actionable states: SCORABLE, PLANNING, ACTION_SELECTED, POLICY_CHECK
        actionable = state is None or state not in non_actionable_states

        return RuleResult(
            rule_id=RuleId.OPPORTUNITY_ACTIONABLE.value,
            passed=actionable,
            reason=(
                None
                if actionable
                else f"Opportunity in non-actionable state: {state}"
            ),
            observed_value=state,
            configured_value="actionable",
        )

    def _check_do_not_contact(
        self, customer_id: str | None, merchant_policy: MerchantPolicy
    ) -> RuleResult:
        """Check if customer is on do-not-contact list."""
        if customer_id is None:
            # No customer ID, can't check - allow (defensive)
            return RuleResult(
                rule_id=RuleId.DO_NOT_CONTACT_CHECK.value,
                passed=True,
                reason=None,
                observed_value=None,
                configured_value=None,
            )

        on_dnc_list = customer_id in merchant_policy.do_not_contact_list
        passed = not on_dnc_list

        return RuleResult(
            rule_id=RuleId.DO_NOT_CONTACT_CHECK.value,
            passed=passed,
            reason=(
                None if passed else "Customer on do-not-contact list"
            ),
            observed_value=on_dnc_list,
            configured_value=False,
        )

    def _check_duplicate_action(
        self,
        merchant_id: str,
        opportunity_id: str,
        action: str,
        execution_state: ExecutionState,
    ) -> RuleResult:
        """Check if action has already been executed."""
        action_key = (merchant_id, opportunity_id, action)
        already_executed = action_key in execution_state.executed_actions

        passed = not already_executed

        return RuleResult(
            rule_id=RuleId.DUPLICATE_ACTION_CHECK.value,
            passed=passed,
            reason=(
                None
                if passed
                else "Action already executed (idempotency violation)"
            ),
            observed_value=already_executed,
            configured_value=False,
        )

    def _check_autonomous_amount_limit(
        self, amount: float, limit: float
    ) -> RuleResult:
        """Check if amount exceeds autonomous limit."""
        passed = amount <= limit

        return RuleResult(
            rule_id=RuleId.AUTONOMOUS_AMOUNT_LIMIT_CHECK.value,
            passed=passed,
            reason=(
                None
                if passed
                else f"Amount ₹{amount:.2f} exceeds autonomous limit ₹{limit:.2f}"
            ),
            observed_value=amount,
            configured_value=limit,
        )

    def _check_max_contacts(
        self,
        merchant_id: str,
        customer_id: str | None,
        simulated_day: int,
        max_contacts: int,
        execution_state: ExecutionState,
    ) -> RuleResult:
        """Check if customer contact limit exceeded."""
        if customer_id is None:
            # No customer ID, can't check - allow (defensive)
            return RuleResult(
                rule_id=RuleId.MAX_CONTACTS_CHECK.value,
                passed=True,
                reason=None,
                observed_value=None,
                configured_value=max_contacts,
            )

        contact_key = (merchant_id, customer_id, simulated_day)
        current_contacts = execution_state.customer_contact_counts.get(
            contact_key, 0
        )

        passed = current_contacts < max_contacts

        return RuleResult(
            rule_id=RuleId.MAX_CONTACTS_CHECK.value,
            passed=passed,
            reason=(
                None
                if passed
                else f"Customer already contacted {current_contacts} times today"
            ),
            observed_value=current_contacts,
            configured_value=max_contacts,
        )

    def _create_decision(
        self,
        decision_type: PolicyDecisionType,
        opportunity_id: str,
        action_type: str,
        evaluated_at: str,
        block_reason: BlockReason | None,
        rule_results: list[RuleResult],
    ) -> PolicyDecision:
        """Create a PolicyDecision."""
        return PolicyDecision(
            decision=decision_type.value,
            opportunity_id=opportunity_id,
            action_type=action_type,
            policy_version=self.policy_version,
            evaluated_at=evaluated_at,
            primary_reason=block_reason.value if block_reason else None,
            all_rule_results=rule_results,
        )
