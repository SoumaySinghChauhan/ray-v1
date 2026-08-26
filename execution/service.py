"""
Execution service for RAY V1.

Manages Payment Link execution with idempotency, state tracking, and audit.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from execution.providers import PaymentLinkExecutor
from execution.types import (
    ExecutionAttempt,
    ExecutionResult,
    ExecutionState,
    OpportunityState,
)
from policy.types import PolicyDecision, PolicyDecisionType


class ExecutionService:
    """
    Execution service for Payment Link creation.

    Handles:
    - Idempotency
    - State tracking
    - Contact count updates
    - Opportunity state transitions
    """

    def __init__(self, executor: PaymentLinkExecutor):
        """
        Initialize execution service.

        Args:
            executor: Payment Link executor (Razorpay or Mock)
        """
        self.executor = executor

        # In-memory storage (TODO: Replace with database)
        self.executions: dict[str, ExecutionAttempt] = {}
        self.execution_keys: dict[str, str] = {}  # idempotency_key -> execution_id
        self.contact_counts: dict[tuple[str, str, int], int] = {}  # (merchant, customer, day) -> count
        self.opportunity_states: dict[str, str] = {}  # opportunity_id -> state

    def execute_allowed_action(
        self,
        policy_decision: PolicyDecision,
        opportunity: dict[str, Any],
        simulated_day: int,
    ) -> ExecutionResult:
        """
        Execute an ALLOWED action.

        Args:
            policy_decision: Policy decision (must be ALLOW)
            opportunity: Opportunity data
            simulated_day: Current simulated day

        Returns:
            ExecutionResult
        """
        # Verify policy decision is ALLOW
        if policy_decision.decision != PolicyDecisionType.ALLOW.value:
            return ExecutionResult(
                success=False,
                execution_id="",
                state=ExecutionState.FAILED.value,
                razorpay_payment_link_id=None,
                reference_id="",
                short_url=None,
                error_message="Action not allowed by policy",
                error_code="POLICY_BLOCKED",
            )

        # Verify action is create_payment_link
        if policy_decision.action_type != "create_payment_link":
            return ExecutionResult(
                success=False,
                execution_id="",
                state=ExecutionState.FAILED.value,
                razorpay_payment_link_id=None,
                reference_id="",
                short_url=None,
                error_message="Only create_payment_link is executable",
                error_code="INVALID_ACTION",
            )

        # Extract data
        merchant_id = opportunity.get("merchant_id", "default_merchant")
        opportunity_id = policy_decision.opportunity_id
        customer_id = opportunity.get("customer_id")
        amount = opportunity.get("amount", 0.0)
        currency = opportunity.get("currency", "INR")

        # Check idempotency
        idempotency_key = self._generate_idempotency_key(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            action_type=policy_decision.action_type,
            policy_version=policy_decision.policy_version,
        )

        # Check if already executed
        existing_execution_id = self.execution_keys.get(idempotency_key)
        if existing_execution_id:
            existing = self.executions.get(existing_execution_id)
            if existing and existing.state == ExecutionState.SUCCEEDED.value:
                # Return existing successful execution
                return ExecutionResult(
                    success=True,
                    execution_id=existing.execution_id,
                    state=existing.state,
                    razorpay_payment_link_id=existing.razorpay_payment_link_id,
                    reference_id=existing.reference_id,
                    short_url=existing.short_url,
                    error_message=None,
                    error_code=None,
                )

        # Extract customer info
        customer_info = None
        if customer_id:
            customer_info = {
                "contact": opportunity.get("customer_contact"),
                "email": opportunity.get("customer_email"),
                "name": opportunity.get("customer_name"),
            }
            # Remove None values
            customer_info = {k: v for k, v in customer_info.items() if v is not None}

        # Execute Payment Link creation
        result = self.executor.create_payment_link(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            amount=amount,
            currency=currency,
            customer_info=customer_info if customer_info else None,
            policy_version=policy_decision.policy_version,
        )

        # Create execution record
        execution_attempt = ExecutionAttempt(
            execution_id=result.execution_id,
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            action_type=policy_decision.action_type,
            policy_version=policy_decision.policy_version,
            state=result.state,
            razorpay_payment_link_id=result.razorpay_payment_link_id,
            reference_id=result.reference_id,
            short_url=result.short_url,
            amount=amount,
            currency=currency,
            created_at=datetime.now(timezone.utc).isoformat(),
            submitted_at=datetime.now(timezone.utc).isoformat() if result.success else None,
            completed_at=datetime.now(timezone.utc).isoformat() if result.success else None,
            expire_by=None,  # TODO: Calculate from expiry_hours
            error_message=result.error_message,
            error_code=result.error_code,
        )

        # Persist execution
        self.executions[result.execution_id] = execution_attempt
        self.execution_keys[idempotency_key] = result.execution_id

        # Update state and counts if successful
        if result.success:
            # Update opportunity state
            self.opportunity_states[opportunity_id] = OpportunityState.ACTION_EXECUTED.value

            # Increment contact count (idempotent)
            if customer_id:
                contact_key = (merchant_id, customer_id, simulated_day)
                if contact_key not in self.contact_counts:
                    self.contact_counts[contact_key] = 1

        return result

    def _generate_idempotency_key(
        self,
        merchant_id: str,
        opportunity_id: str,
        action_type: str,
        policy_version: str,
    ) -> str:
        """
        Generate deterministic idempotency key.

        Args:
            merchant_id: Merchant ID
            opportunity_id: Opportunity ID
            action_type: Action type
            policy_version: Policy version

        Returns:
            Idempotency key (SHA256 hash)
        """
        key_input = f"{merchant_id}:{opportunity_id}:{action_type}:{policy_version}"
        return hashlib.sha256(key_input.encode()).hexdigest()

    def get_execution(self, execution_id: str) -> ExecutionAttempt | None:
        """Get execution by ID."""
        return self.executions.get(execution_id)

    def get_execution_by_reference_id(self, reference_id: str) -> ExecutionAttempt | None:
        """Get execution by Razorpay reference_id."""
        for execution in self.executions.values():
            if execution.reference_id == reference_id:
                return execution
        return None

    def get_execution_by_payment_link_id(self, payment_link_id: str) -> ExecutionAttempt | None:
        """Get execution by Razorpay Payment Link ID."""
        for execution in self.executions.values():
            if execution.razorpay_payment_link_id == payment_link_id:
                return execution
        return None

    def get_contact_count(
        self, merchant_id: str, customer_id: str, simulated_day: int
    ) -> int:
        """Get customer contact count for day."""
        contact_key = (merchant_id, customer_id, simulated_day)
        return self.contact_counts.get(contact_key, 0)

    def get_opportunity_state(self, opportunity_id: str) -> str | None:
        """Get opportunity state."""
        return self.opportunity_states.get(opportunity_id)
