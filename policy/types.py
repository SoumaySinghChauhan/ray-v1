"""
Policy engine types for RAY V1.

The policy engine is the deterministic authorization layer that evaluates
whether an economically-selected action is permitted.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PolicyDecisionType(str, Enum):
    """Policy decision outcomes."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class BlockReason(str, Enum):
    """Constrained vocabulary for block reasons."""

    # Rule violations (in evaluation order)
    INVALID_ACTION = "INVALID_ACTION"
    OPPORTUNITY_NOT_ACTIONABLE = "OPPORTUNITY_NOT_ACTIONABLE"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    DUPLICATE_ACTION = "DUPLICATE_ACTION"
    AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED = "AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED"
    MAX_CONTACTS_EXCEEDED = "MAX_CONTACTS_EXCEEDED"
    DAILY_CAPACITY_EXCEEDED = "DAILY_CAPACITY_EXCEEDED"


class RuleId(str, Enum):
    """Policy rule identifiers."""

    VALID_ACTION_TYPE = "VALID_ACTION_TYPE"
    OPPORTUNITY_ACTIONABLE = "OPPORTUNITY_ACTIONABLE"
    DO_NOT_CONTACT_CHECK = "DO_NOT_CONTACT_CHECK"
    DUPLICATE_ACTION_CHECK = "DUPLICATE_ACTION_CHECK"
    AUTONOMOUS_AMOUNT_LIMIT_CHECK = "AUTONOMOUS_AMOUNT_LIMIT_CHECK"
    MAX_CONTACTS_CHECK = "MAX_CONTACTS_CHECK"
    DAILY_CAPACITY_CHECK = "DAILY_CAPACITY_CHECK"


@dataclass
class RuleResult:
    """Result of evaluating a single policy rule."""

    rule_id: str
    passed: bool
    reason: str | None
    observed_value: Any | None
    configured_value: Any | None


@dataclass
class PolicyDecision:
    """
    Policy decision for a single action.

    The policy engine evaluates whether an optimizer-selected action
    is permitted under merchant policy constraints.
    """

    decision: str  # ALLOW or BLOCK
    opportunity_id: str
    action_type: str
    policy_version: str
    evaluated_at: str
    primary_reason: str | None  # BlockReason if BLOCK, None if ALLOW
    all_rule_results: list[RuleResult]


@dataclass
class PolicyEvaluationResult:
    """
    Result of evaluating an entire optimization plan.

    Contains all allowed and blocked actions with their reasons.
    """

    plan_id: str
    policy_version: str
    evaluated_at: str

    # Actions
    allowed_actions: list[PolicyDecision]
    blocked_actions: list[PolicyDecision]

    # Summary statistics
    total_evaluated: int
    total_allowed: int
    total_blocked: int

    # Block reason breakdown
    block_reasons: dict[str, int]


@dataclass
class ExecutionState:
    """
    Execution and idempotency state for policy evaluation.

    Tracks:
    - Which actions have been executed
    - Customer contact counts per day
    - Opportunity states
    """

    # Idempotency: (merchant_id, opportunity_id, action_type) -> executed
    executed_actions: set[tuple[str, str, str]]

    # Contact tracking: (merchant_id, customer_id, simulated_day) -> count
    customer_contact_counts: dict[tuple[str, str, int], int]

    # Opportunity states: opportunity_id -> state
    opportunity_states: dict[str, str]

    @staticmethod
    def create_empty() -> "ExecutionState":
        """Create empty execution state for testing."""
        return ExecutionState(
            executed_actions=set(),
            customer_contact_counts={},
            opportunity_states={},
        )


@dataclass
class MerchantPolicy:
    """
    Merchant-specific policy configuration.

    Encapsulates all policy parameters for a merchant.
    """

    merchant_id: str
    max_actions_per_day: int
    max_contacts_per_customer_per_day: int
    autonomous_amount_limit: float  # INR
    policy_version: str

    # Do-not-contact list: set of customer_ids
    do_not_contact_list: set[str]
