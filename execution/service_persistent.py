"""
Persistent execution service for RAY V1.

Database-backed execution service that survives process restarts.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from execution.providers import PaymentLinkExecutor
from execution.types import (
    ExecutionAttempt,
    ExecutionResult,
    ExecutionState,
    OpportunityState,
)
from policy.types import PolicyDecision, PolicyDecisionType


# Import database models
import sys
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray/services/api')
from database.models import (
    ExecutionAttemptExtended,
    ContactCount,
    ExecutionStateEnum,
)


def _execution_model_to_dataclass(model: ExecutionAttemptExtended) -> ExecutionAttempt:
    """Convert database model to dataclass."""
    return ExecutionAttempt(
        execution_id=model.id,
        merchant_id=model.merchant_id,
        opportunity_id=model.opportunity_id,
        action_type=model.action_type,
        policy_version=model.policy_version,
        state=model.state.value if isinstance(model.state, ExecutionStateEnum) else model.state,
        razorpay_payment_link_id=model.razorpay_payment_link_id,
        reference_id=model.reference_id,
        short_url=model.short_url,
        amount=float(model.amount),
        currency=model.currency,
        created_at=model.created_at.isoformat() if model.created_at else None,
        submitted_at=model.submitted_at.isoformat() if model.submitted_at else None,
        completed_at=model.completed_at.isoformat() if model.completed_at else None,
        expire_by=model.expire_by.isoformat() if model.expire_by else None,
        error_message=model.error_message,
        error_code=model.error_code,
    )


class PersistentExecutionService:
    """
    Database-backed execution service.

    All state persisted to database. Survives process restarts.
    """

    def __init__(self, executor: PaymentLinkExecutor, db_session: Session):
        """
        Initialize persistent execution service.

        Args:
            executor: Payment Link executor (Razorpay or Mock)
            db_session: SQLAlchemy database session
        """
        self.executor = executor
        self.db = db_session

    def execute_allowed_action(
        self,
        policy_decision: PolicyDecision,
        opportunity: dict[str, Any],
        simulated_day: int,
    ) -> ExecutionResult:
        """
        Execute an ALLOWED action with database persistence.

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

        # Check idempotency (query database)
        idempotency_key = self._generate_idempotency_key(
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            action_type=policy_decision.action_type,
            policy_version=policy_decision.policy_version,
        )

        # Check if already executed (database query)
        existing = (
            self.db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.idempotency_key == idempotency_key)
            .first()
        )

        if existing and existing.state == ExecutionStateEnum.SUCCEEDED:
            # Return existing successful execution
            return ExecutionResult(
                success=True,
                execution_id=existing.id,
                state=existing.state.value,
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

        # Create execution record in database
        execution_model = ExecutionAttemptExtended(
            id=result.execution_id,
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            action_type=policy_decision.action_type,
            policy_version=policy_decision.policy_version,
            idempotency_key=idempotency_key,
            reference_id=result.reference_id,
            razorpay_payment_link_id=result.razorpay_payment_link_id,
            short_url=result.short_url,
            state=ExecutionStateEnum[result.state],
            amount=amount,
            currency=currency,
            created_at=datetime.utcnow(),
            submitted_at=datetime.utcnow() if result.success else None,
            completed_at=datetime.utcnow() if result.success else None,
            expire_by=None,
            error_message=result.error_message,
            error_code=result.error_code,
        )

        try:
            self.db.add(execution_model)
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            # Race condition: another process created execution
            # Query and return existing
            existing = (
                self.db.query(ExecutionAttemptExtended)
                .filter(ExecutionAttemptExtended.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return ExecutionResult(
                    success=True,
                    execution_id=existing.id,
                    state=existing.state.value,
                    razorpay_payment_link_id=existing.razorpay_payment_link_id,
                    reference_id=existing.reference_id,
                    short_url=existing.short_url,
                    error_message=None,
                    error_code=None,
                )
            raise  # Unexpected integrity error

        # Update contact count if successful (idempotent)
        if result.success and customer_id:
            self._increment_contact_count(merchant_id, customer_id, simulated_day)

        return result

    def _increment_contact_count(
        self, merchant_id: str, customer_id: str, simulated_day: int
    ) -> None:
        """
        Increment contact count (database-backed, idempotent).

        Uses ON CONFLICT DO UPDATE for idempotency.
        """
        # Try to insert
        contact_count = ContactCount(
            merchant_id=merchant_id,
            customer_id=customer_id,
            simulated_day=simulated_day,
            contact_count=1,
            updated_at=datetime.utcnow(),
        )

        # Check if exists
        existing = (
            self.db.query(ContactCount)
            .filter(
                ContactCount.merchant_id == merchant_id,
                ContactCount.customer_id == customer_id,
                ContactCount.simulated_day == simulated_day,
            )
            .first()
        )

        if existing:
            # Already exists, don't increment again (idempotent)
            return

        try:
            self.db.add(contact_count)
            self.db.commit()
        except IntegrityError:
            # Race condition: another process incremented
            self.db.rollback()

    def _generate_idempotency_key(
        self,
        merchant_id: str,
        opportunity_id: str,
        action_type: str,
        policy_version: str,
    ) -> str:
        """Generate deterministic idempotency key."""
        key_input = f"{merchant_id}:{opportunity_id}:{action_type}:{policy_version}"
        return hashlib.sha256(key_input.encode()).hexdigest()

    def get_execution(self, execution_id: str) -> Optional[ExecutionAttempt]:
        """Get execution by ID (database query)."""
        model = (
            self.db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.id == execution_id)
            .first()
        )
        if model:
            return _execution_model_to_dataclass(model)
        return None

    def get_execution_by_reference_id(self, reference_id: str) -> Optional[ExecutionAttempt]:
        """Get execution by Razorpay reference_id (database query)."""
        model = (
            self.db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.reference_id == reference_id)
            .first()
        )
        if model:
            return _execution_model_to_dataclass(model)
        return None

    def get_execution_by_payment_link_id(
        self, payment_link_id: str
    ) -> Optional[ExecutionAttempt]:
        """Get execution by Razorpay Payment Link ID (database query)."""
        model = (
            self.db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.razorpay_payment_link_id == payment_link_id)
            .first()
        )
        if model:
            return _execution_model_to_dataclass(model)
        return None

    def get_contact_count(
        self, merchant_id: str, customer_id: str, simulated_day: int
    ) -> int:
        """Get customer contact count for day (database query)."""
        model = (
            self.db.query(ContactCount)
            .filter(
                ContactCount.merchant_id == merchant_id,
                ContactCount.customer_id == customer_id,
                ContactCount.simulated_day == simulated_day,
            )
            .first()
        )
        if model:
            return model.contact_count
        return 0

    def get_opportunity_state(self, opportunity_id: str) -> Optional[str]:
        """
        Get opportunity state from most recent outcome.

        Infers state from RecoveryOutcomeExtended table.
        """
        # Import here to avoid circular dependency
        from database.models import RecoveryOutcomeExtended, OutcomeTypeEnum

        outcome = (
            self.db.query(RecoveryOutcomeExtended)
            .filter(RecoveryOutcomeExtended.opportunity_id == opportunity_id)
            .order_by(RecoveryOutcomeExtended.observed_at.desc())
            .first()
        )

        if not outcome:
            # Check if execution exists
            execution = (
                self.db.query(ExecutionAttemptExtended)
                .filter(ExecutionAttemptExtended.opportunity_id == opportunity_id)
                .first()
            )
            if execution and execution.state == ExecutionStateEnum.SUCCEEDED:
                return OpportunityState.ACTION_EXECUTED.value
            return None

        # Map outcome to opportunity state
        outcome_to_state = {
            OutcomeTypeEnum.RECOVERED: OpportunityState.RECOVERED.value,
            OutcomeTypeEnum.PARTIALLY_RECOVERED: OpportunityState.PARTIALLY_RECOVERED.value,
            OutcomeTypeEnum.EXPIRED: OpportunityState.EXPIRED.value,
            OutcomeTypeEnum.CANCELLED: OpportunityState.CANCELLED.value,
        }

        return outcome_to_state.get(outcome.outcome_type)
