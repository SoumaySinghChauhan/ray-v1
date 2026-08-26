"""
Persistent webhook handler for RAY V1.

Database-backed webhook processing that survives process restarts.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from execution.providers import verify_webhook_signature
from execution.service_persistent import PersistentExecutionService
from execution.types import (
    WebhookEventType,
    OpportunityState,
)


# Import database models
import sys
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray/services/api')
from database.models import (
    WebhookEventExtended,
    RecoveryOutcomeExtended,
    WebhookProcessingStatusEnum,
    OutcomeTypeEnum,
)


class PersistentWebhookHandler:
    """
    Database-backed webhook handler.

    All webhook events and outcomes persisted to database.
    Survives process restarts.
    """

    def __init__(
        self,
        execution_service: PersistentExecutionService,
        webhook_secret: str,
        db_session: Session,
    ):
        """
        Initialize persistent webhook handler.

        Args:
            execution_service: Persistent execution service
            webhook_secret: Razorpay webhook secret
            db_session: SQLAlchemy database session
        """
        self.execution_service = execution_service
        self.webhook_secret = webhook_secret
        self.db = db_session

    def process_webhook(
        self,
        raw_body: bytes,
        signature: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process webhook event with database persistence.

        Args:
            raw_body: Raw request body (for signature verification)
            signature: X-Razorpay-Signature header
            payload: Parsed JSON payload

        Returns:
            Processing result
        """
        webhook_id = str(uuid.uuid4())
        received_at = datetime.utcnow()

        # Extract event info early (before signature verification)
        # so failed webhooks also get unique event_id
        event_id = payload.get("id", payload.get("event", ""))
        event_type = payload.get("event", "")

        # Step 1: Verify signature
        if not self.webhook_secret:
            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": "Webhook secret not configured",
            }

        signature_valid = verify_webhook_signature(
            payload_body=raw_body,
            signature=signature,
            secret=self.webhook_secret,
        )

        if not signature_valid:
            # Record failed verification with actual event_id
            webhook_event = WebhookEventExtended(
                id=webhook_id,
                provider="razorpay",
                event_id=event_id if event_id else webhook_id,  # Use webhook_id as fallback
                event_type=event_type,
                payload=payload,
                payload_hash=self._hash_payload(raw_body),
                signature_verified=False,
                processing_status=WebhookProcessingStatusEnum.FAILED,
                received_at=received_at,
                error_message="Invalid signature",
            )
            self.db.add(webhook_event)
            self.db.commit()

            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": "Invalid signature",
            }

        # Step 2: Already extracted event info above
        entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})

        # Step 3: Check idempotency (database query)
        existing_event = (
            self.db.query(WebhookEventExtended)
            .filter(
                WebhookEventExtended.provider == "razorpay",
                WebhookEventExtended.event_id == event_id,
            )
            .first()
        )

        if existing_event:
            # Duplicate event
            return {
                "success": True,
                "webhook_id": existing_event.id,
                "status": "duplicate",
                "message": "Event already processed",
            }

        # Step 4: Create webhook event record
        webhook_event = WebhookEventExtended(
            id=webhook_id,
            provider="razorpay",
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            payload_hash=self._hash_payload(raw_body),
            signature_verified=True,
            processing_status=WebhookProcessingStatusEnum.VERIFIED,
            received_at=received_at,
        )

        try:
            self.db.add(webhook_event)
            self.db.commit()
        except IntegrityError:
            # Race condition: another process created event
            self.db.rollback()
            return {
                "success": True,
                "webhook_id": webhook_id,
                "status": "duplicate",
                "message": "Event already processed (race)",
            }

        # Step 5: Resolve execution and opportunity
        payment_link_id = entity.get("id")
        reference_id = entity.get("reference_id")

        execution = None
        if payment_link_id:
            execution = self.execution_service.get_execution_by_payment_link_id(payment_link_id)
        if not execution and reference_id:
            execution = self.execution_service.get_execution_by_reference_id(reference_id)

        if not execution:
            # Unmatched event
            webhook_event.processing_status = WebhookProcessingStatusEnum.FAILED
            webhook_event.error_message = "Execution not found for Payment Link"
            self.db.commit()

            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": "Execution not found",
            }

        webhook_event.execution_id = execution.execution_id
        webhook_event.opportunity_id = execution.opportunity_id
        webhook_event.razorpay_payment_link_id = payment_link_id
        webhook_event.reference_id = reference_id
        self.db.commit()

        # Step 6: Process event by type
        try:
            if event_type == WebhookEventType.PAYMENT_LINK_PAID.value:
                self._handle_paid(webhook_event, execution, entity)
            elif event_type == WebhookEventType.PAYMENT_LINK_PARTIALLY_PAID.value:
                self._handle_partially_paid(webhook_event, execution, entity)
            elif event_type == WebhookEventType.PAYMENT_LINK_CANCELLED.value:
                self._handle_cancelled(webhook_event, execution, entity)
            elif event_type == WebhookEventType.PAYMENT_LINK_EXPIRED.value:
                self._handle_expired(webhook_event, execution, entity)
            else:
                webhook_event.processing_status = WebhookProcessingStatusEnum.FAILED
                webhook_event.error_message = f"Unknown event type: {event_type}"
                self.db.commit()

                return {
                    "success": False,
                    "webhook_id": webhook_id,
                    "error": f"Unknown event type: {event_type}",
                }

            webhook_event.processing_status = WebhookProcessingStatusEnum.PROCESSED
            webhook_event.processed_at = datetime.utcnow()
            self.db.commit()

            return {
                "success": True,
                "webhook_id": webhook_id,
                "event_type": event_type,
                "opportunity_id": execution.opportunity_id,
            }

        except Exception as e:
            webhook_event.processing_status = WebhookProcessingStatusEnum.FAILED
            webhook_event.error_message = str(e)
            self.db.commit()

            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": str(e),
            }

    def _handle_paid(
        self,
        webhook_event: WebhookEventExtended,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.paid event with database persistence."""
        opportunity_id = execution.opportunity_id
        payment_id = entity.get("payment_id")
        amount_paid = entity.get("amount_paid", 0) / 100.0  # Convert from paise

        # Check for stale events (don't overwrite RECOVERED)
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state == OpportunityState.RECOVERED.value:
            # Already recovered, ignore stale event
            return

        # Check if outcome already exists for this event
        existing_outcome = (
            self.db.query(RecoveryOutcomeExtended)
            .filter(RecoveryOutcomeExtended.source_event_id == webhook_event.event_id)
            .first()
        )
        if existing_outcome:
            # Outcome already created (idempotent)
            return

        # Create recovery outcome
        outcome = RecoveryOutcomeExtended(
            id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeTypeEnum.RECOVERED,
            amount_recovered=amount_paid,
            currency=execution.currency,
            razorpay_payment_id=payment_id,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        self.db.add(outcome)
        self.db.commit()

    def _handle_partially_paid(
        self,
        webhook_event: WebhookEventExtended,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.partially_paid event."""
        opportunity_id = execution.opportunity_id
        payment_id = entity.get("payment_id")
        amount_paid = entity.get("amount_paid", 0) / 100.0

        # Check for stale events
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state in [
            OpportunityState.RECOVERED.value,
            OpportunityState.PARTIALLY_RECOVERED.value,
        ]:
            return

        # Check if outcome already exists
        existing_outcome = (
            self.db.query(RecoveryOutcomeExtended)
            .filter(RecoveryOutcomeExtended.source_event_id == webhook_event.event_id)
            .first()
        )
        if existing_outcome:
            return

        # Create recovery outcome
        outcome = RecoveryOutcomeExtended(
            id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeTypeEnum.PARTIALLY_RECOVERED,
            amount_recovered=amount_paid,
            currency=execution.currency,
            razorpay_payment_id=payment_id,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        self.db.add(outcome)
        self.db.commit()

    def _handle_cancelled(
        self,
        webhook_event: WebhookEventExtended,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.cancelled event."""
        opportunity_id = execution.opportunity_id

        # Check for stale events
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state in [
            OpportunityState.RECOVERED.value,
            OpportunityState.PARTIALLY_RECOVERED.value,
        ]:
            return

        # Check if outcome already exists
        existing_outcome = (
            self.db.query(RecoveryOutcomeExtended)
            .filter(RecoveryOutcomeExtended.source_event_id == webhook_event.event_id)
            .first()
        )
        if existing_outcome:
            return

        # Create recovery outcome
        outcome = RecoveryOutcomeExtended(
            id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeTypeEnum.CANCELLED,
            amount_recovered=0.0,
            currency=execution.currency,
            razorpay_payment_id=None,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        self.db.add(outcome)
        self.db.commit()

    def _handle_expired(
        self,
        webhook_event: WebhookEventExtended,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.expired event."""
        opportunity_id = execution.opportunity_id

        # Check for stale events
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state in [
            OpportunityState.RECOVERED.value,
            OpportunityState.PARTIALLY_RECOVERED.value,
        ]:
            return

        # Check if outcome already exists
        existing_outcome = (
            self.db.query(RecoveryOutcomeExtended)
            .filter(RecoveryOutcomeExtended.source_event_id == webhook_event.event_id)
            .first()
        )
        if existing_outcome:
            return

        # Create recovery outcome
        outcome = RecoveryOutcomeExtended(
            id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeTypeEnum.EXPIRED,
            amount_recovered=0.0,
            currency=execution.currency,
            razorpay_payment_id=None,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        self.db.add(outcome)
        self.db.commit()

    def _hash_payload(self, payload_body: bytes) -> str:
        """Hash payload for deduplication."""
        return hashlib.sha256(payload_body).hexdigest()

    def get_outcome_by_opportunity(self, opportunity_id: str) -> Optional[RecoveryOutcomeExtended]:
        """Get recovery outcome for opportunity (database query)."""
        return (
            self.db.query(RecoveryOutcomeExtended)
            .filter(RecoveryOutcomeExtended.opportunity_id == opportunity_id)
            .order_by(RecoveryOutcomeExtended.observed_at.desc())
            .first()
        )
