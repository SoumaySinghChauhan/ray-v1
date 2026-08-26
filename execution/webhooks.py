"""
Razorpay webhook handler for RAY V1.

Processes Payment Link webhook events with signature verification and idempotency.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from execution.providers import verify_webhook_signature
from execution.service import ExecutionService
from execution.types import (
    WebhookEvent,
    WebhookEventType,
    WebhookProcessingStatus,
    RecoveryOutcome,
    OutcomeType,
    OpportunityState,
)


class WebhookHandler:
    """
    Razorpay webhook handler.

    Processes webhook events with:
    - Signature verification
    - Idempotency
    - State updates
    - Recovery outcomes
    """

    def __init__(self, execution_service: ExecutionService, webhook_secret: str):
        """
        Initialize webhook handler.

        Args:
            execution_service: Execution service
            webhook_secret: Razorpay webhook secret for signature verification
        """
        self.execution_service = execution_service
        self.webhook_secret = webhook_secret

        # In-memory storage (TODO: Replace with database)
        self.webhook_events: dict[str, WebhookEvent] = {}  # webhook_id -> event
        self.event_ids: set[str] = set()  # Track processed event IDs
        self.recovery_outcomes: dict[str, RecoveryOutcome] = {}  # outcome_id -> outcome

    def process_webhook(
        self,
        raw_body: bytes,
        signature: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process webhook event.

        Args:
            raw_body: Raw request body (for signature verification)
            signature: X-Razorpay-Signature header
            payload: Parsed JSON payload

        Returns:
            Processing result
        """
        webhook_id = str(uuid.uuid4())
        received_at = datetime.now(timezone.utc).isoformat()

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
            # Record failed verification
            webhook_event = WebhookEvent(
                webhook_id=webhook_id,
                provider="razorpay",
                event_id="",
                event_type="",
                payload=payload,
                payload_hash=self._hash_payload(raw_body),
                received_at=received_at,
                signature_verified=False,
                processing_status=WebhookProcessingStatus.FAILED.value,
                execution_id=None,
                opportunity_id=None,
                error_message="Invalid signature",
            )
            self.webhook_events[webhook_id] = webhook_event

            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": "Invalid signature",
            }

        # Step 2: Extract event info
        event_id = payload.get("id", payload.get("event"))  # Use id if available, fallback to event
        event_type = payload.get("event")
        entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})

        # Step 3: Check idempotency
        if event_id in self.event_ids:
            # Duplicate event
            webhook_event = WebhookEvent(
                webhook_id=webhook_id,
                provider="razorpay",
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                payload_hash=self._hash_payload(raw_body),
                received_at=received_at,
                signature_verified=True,
                processing_status=WebhookProcessingStatus.DUPLICATE.value,
                execution_id=None,
                opportunity_id=None,
                error_message=None,
            )
            self.webhook_events[webhook_id] = webhook_event

            return {
                "success": True,
                "webhook_id": webhook_id,
                "status": "duplicate",
                "message": "Event already processed",
            }

        # Step 4: Record event as received
        webhook_event = WebhookEvent(
            webhook_id=webhook_id,
            provider="razorpay",
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            payload_hash=self._hash_payload(raw_body),
            received_at=received_at,
            signature_verified=True,
            processing_status=WebhookProcessingStatus.VERIFIED.value,
            execution_id=None,
            opportunity_id=None,
            error_message=None,
        )
        self.webhook_events[webhook_id] = webhook_event
        self.event_ids.add(event_id)

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
            webhook_event.processing_status = WebhookProcessingStatus.FAILED.value
            webhook_event.error_message = "Execution not found for Payment Link"
            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": "Execution not found",
            }

        webhook_event.execution_id = execution.execution_id
        webhook_event.opportunity_id = execution.opportunity_id

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
                webhook_event.processing_status = WebhookProcessingStatus.FAILED.value
                webhook_event.error_message = f"Unknown event type: {event_type}"
                return {
                    "success": False,
                    "webhook_id": webhook_id,
                    "error": f"Unknown event type: {event_type}",
                }

            webhook_event.processing_status = WebhookProcessingStatus.PROCESSED.value

            return {
                "success": True,
                "webhook_id": webhook_id,
                "event_type": event_type,
                "opportunity_id": execution.opportunity_id,
            }

        except Exception as e:
            webhook_event.processing_status = WebhookProcessingStatus.FAILED.value
            webhook_event.error_message = str(e)
            return {
                "success": False,
                "webhook_id": webhook_id,
                "error": str(e),
            }

    def _handle_paid(
        self,
        webhook_event: WebhookEvent,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.paid event."""
        opportunity_id = execution.opportunity_id
        payment_id = entity.get("payment_id")
        amount_paid = entity.get("amount_paid", 0) / 100.0  # Convert from paise

        # Check for stale events (don't overwrite RECOVERED)
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state == OpportunityState.RECOVERED.value:
            # Already recovered, ignore stale event
            return

        # Create recovery outcome
        outcome = RecoveryOutcome(
            outcome_id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeType.RECOVERED.value,
            amount_recovered=amount_paid,
            currency=execution.currency,
            razorpay_payment_id=payment_id,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
            notes=None,
        )

        self.recovery_outcomes[outcome.outcome_id] = outcome

        # Update opportunity state
        self.execution_service.opportunity_states[opportunity_id] = OpportunityState.RECOVERED.value

    def _handle_partially_paid(
        self,
        webhook_event: WebhookEvent,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.partially_paid event."""
        opportunity_id = execution.opportunity_id
        payment_id = entity.get("payment_id")
        amount_paid = entity.get("amount_paid", 0) / 100.0  # Convert from paise

        # Check for stale events
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state in [OpportunityState.RECOVERED.value, OpportunityState.PARTIALLY_RECOVERED.value]:
            # Already recovered/partially recovered, check if this is newer
            return

        # Create recovery outcome
        outcome = RecoveryOutcome(
            outcome_id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeType.PARTIALLY_RECOVERED.value,
            amount_recovered=amount_paid,
            currency=execution.currency,
            razorpay_payment_id=payment_id,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
            notes=None,
        )

        self.recovery_outcomes[outcome.outcome_id] = outcome

        # Update opportunity state
        self.execution_service.opportunity_states[opportunity_id] = (
            OpportunityState.PARTIALLY_RECOVERED.value
        )

    def _handle_cancelled(
        self,
        webhook_event: WebhookEvent,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.cancelled event."""
        opportunity_id = execution.opportunity_id

        # Check for stale events (don't overwrite terminal states)
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state in [
            OpportunityState.RECOVERED.value,
            OpportunityState.PARTIALLY_RECOVERED.value,
        ]:
            # Already recovered, ignore cancelled event
            return

        # Create recovery outcome
        outcome = RecoveryOutcome(
            outcome_id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeType.CANCELLED.value,
            amount_recovered=0.0,
            currency=execution.currency,
            razorpay_payment_id=None,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
            notes=None,
        )

        self.recovery_outcomes[outcome.outcome_id] = outcome

        # Update opportunity state
        self.execution_service.opportunity_states[opportunity_id] = OpportunityState.CANCELLED.value

    def _handle_expired(
        self,
        webhook_event: WebhookEvent,
        execution: Any,
        entity: dict[str, Any],
    ) -> None:
        """Handle payment_link.expired event."""
        opportunity_id = execution.opportunity_id

        # Check for stale events (don't overwrite terminal states)
        current_state = self.execution_service.get_opportunity_state(opportunity_id)
        if current_state in [
            OpportunityState.RECOVERED.value,
            OpportunityState.PARTIALLY_RECOVERED.value,
        ]:
            # Already recovered, ignore expired event
            return

        # Create recovery outcome
        outcome = RecoveryOutcome(
            outcome_id=str(uuid.uuid4()),
            opportunity_id=opportunity_id,
            execution_id=execution.execution_id,
            outcome_type=OutcomeType.EXPIRED.value,
            amount_recovered=0.0,
            currency=execution.currency,
            razorpay_payment_id=None,
            razorpay_payment_link_id=execution.razorpay_payment_link_id,
            source_event_id=webhook_event.event_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
            notes=None,
        )

        self.recovery_outcomes[outcome.outcome_id] = outcome

        # Update opportunity state
        self.execution_service.opportunity_states[opportunity_id] = OpportunityState.EXPIRED.value

    def _hash_payload(self, payload_body: bytes) -> str:
        """Hash payload for deduplication."""
        return hashlib.sha256(payload_body).hexdigest()

    def get_outcome_by_opportunity(self, opportunity_id: str) -> RecoveryOutcome | None:
        """Get recovery outcome for opportunity."""
        for outcome in self.recovery_outcomes.values():
            if outcome.opportunity_id == opportunity_id:
                return outcome
        return None
