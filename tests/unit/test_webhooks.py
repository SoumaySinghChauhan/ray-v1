"""
Tests for webhook handler.

Verifies:
- Signature verification
- Event processing
- Idempotency
- Recovery outcomes
- Stale event protection
"""

import pytest
import json
import hmac
import hashlib

from execution.service import ExecutionService
from execution.providers import MockPaymentLinkExecutor, verify_webhook_signature
from execution.webhooks import WebhookHandler
from execution.types import (
    ExecutionAttempt,
    ExecutionState,
    WebhookEventType,
    WebhookProcessingStatus,
    OutcomeType,
    OpportunityState,
)
from policy.types import PolicyDecision, PolicyDecisionType
from datetime import datetime, timezone


@pytest.fixture
def webhook_secret():
    """Webhook secret for testing."""
    return "test_webhook_secret_12345"


@pytest.fixture
def execution_service():
    """Create execution service."""
    executor = MockPaymentLinkExecutor(should_succeed=True)
    return ExecutionService(executor=executor)


@pytest.fixture
def webhook_handler(execution_service, webhook_secret):
    """Create webhook handler."""
    return WebhookHandler(
        execution_service=execution_service,
        webhook_secret=webhook_secret,
    )


def create_webhook_payload(
    event_type: str,
    payment_link_id: str,
    reference_id: str,
    amount: int = 1000000,  # paise
    payment_id: str | None = None,
    event_id: str | None = None,
) -> dict:
    """Create webhook payload."""
    import uuid
    payload = {
        "id": event_id if event_id else f"evt_{uuid.uuid4().hex[:16]}",
        "event": event_type,
        "payload": {
            "payment_link": {
                "entity": {
                    "id": payment_link_id,
                    "reference_id": reference_id,
                    "amount": amount,
                    "amount_paid": amount if payment_id else 0,
                    "payment_id": payment_id,
                }
            }
        },
    }
    return payload


def sign_payload(payload: dict, secret: str) -> tuple[bytes, str]:
    """Sign webhook payload."""
    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        key=secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return payload_bytes, signature


def create_mock_execution(
    execution_service: ExecutionService,
    opportunity_id: str,
    payment_link_id: str,
    reference_id: str,
) -> ExecutionAttempt:
    """Create mock execution in service."""
    execution = ExecutionAttempt(
        execution_id=f"exec_{opportunity_id}",
        merchant_id="test_merchant",
        opportunity_id=opportunity_id,
        action_type="create_payment_link",
        policy_version="1.0.0",
        state=ExecutionState.SUCCEEDED.value,
        razorpay_payment_link_id=payment_link_id,
        reference_id=reference_id,
        short_url=f"https://rzp.io/l/{payment_link_id}",
        amount=10000.0,
        currency="INR",
        created_at=datetime.now(timezone.utc).isoformat(),
        submitted_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        expire_by=None,
        error_message=None,
        error_code=None,
    )
    execution_service.executions[execution.execution_id] = execution
    execution_service.opportunity_states[opportunity_id] = OpportunityState.ACTION_EXECUTED.value
    return execution


class TestSignatureVerification:
    """Test webhook signature verification."""

    def test_valid_signature(self, webhook_secret):
        """Test 1: Valid signature passes verification."""
        payload = {"event": "test"}
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        result = verify_webhook_signature(
            payload_body=payload_bytes,
            signature=signature,
            secret=webhook_secret,
        )

        assert result is True

    def test_invalid_signature(self, webhook_secret):
        """Test 2: Invalid signature fails verification."""
        payload = {"event": "test"}
        payload_bytes = json.dumps(payload).encode()
        invalid_signature = "invalid_signature_12345"

        result = verify_webhook_signature(
            payload_body=payload_bytes,
            signature=invalid_signature,
            secret=webhook_secret,
        )

        assert result is False

    def test_modified_payload_fails(self, webhook_secret):
        """Test 3: Modified payload fails verification."""
        payload = {"event": "test"}
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        # Modify payload
        modified_payload = {"event": "modified"}
        modified_bytes = json.dumps(modified_payload).encode()

        result = verify_webhook_signature(
            payload_body=modified_bytes,
            signature=signature,
            secret=webhook_secret,
        )

        assert result is False


class TestWebhookProcessing:
    """Test webhook event processing."""

    def test_paid_event_creates_outcome(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 4: payment_link.paid creates RECOVERED outcome."""
        # Create execution
        payment_link_id = "plink_test_001"
        reference_id = "RAY-opp-001"
        execution = create_mock_execution(
            execution_service, "opp_001", payment_link_id, reference_id
        )

        # Create webhook payload
        payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_PAID.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            amount=1000000,
            payment_id="pay_test_001",
        )
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        # Process webhook
        result = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )

        assert result["success"] is True
        assert result["event_type"] == WebhookEventType.PAYMENT_LINK_PAID.value

        # Verify outcome created
        outcome = webhook_handler.get_outcome_by_opportunity("opp_001")
        assert outcome is not None
        assert outcome.outcome_type == OutcomeType.RECOVERED.value
        assert outcome.amount_recovered == 10000.0
        assert outcome.razorpay_payment_id == "pay_test_001"

        # Verify opportunity state
        state = execution_service.get_opportunity_state("opp_001")
        assert state == OpportunityState.RECOVERED.value

    def test_partially_paid_event(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 5: payment_link.partially_paid creates PARTIALLY_RECOVERED outcome."""
        # Create execution
        payment_link_id = "plink_test_002"
        reference_id = "RAY-opp-002"
        execution = create_mock_execution(
            execution_service, "opp_002", payment_link_id, reference_id
        )

        # Create webhook payload
        payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_PARTIALLY_PAID.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            amount=500000,  # Half payment
            payment_id="pay_test_002",
        )
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        # Process webhook
        result = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )

        assert result["success"] is True

        # Verify outcome
        outcome = webhook_handler.get_outcome_by_opportunity("opp_002")
        assert outcome is not None
        assert outcome.outcome_type == OutcomeType.PARTIALLY_RECOVERED.value
        assert outcome.amount_recovered == 5000.0

        # Verify opportunity state
        state = execution_service.get_opportunity_state("opp_002")
        assert state == OpportunityState.PARTIALLY_RECOVERED.value

    def test_cancelled_event(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 6: payment_link.cancelled creates CANCELLED outcome."""
        # Create execution
        payment_link_id = "plink_test_003"
        reference_id = "RAY-opp-003"
        execution = create_mock_execution(
            execution_service, "opp_003", payment_link_id, reference_id
        )

        # Create webhook payload
        payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_CANCELLED.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
        )
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        # Process webhook
        result = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )

        assert result["success"] is True

        # Verify outcome
        outcome = webhook_handler.get_outcome_by_opportunity("opp_003")
        assert outcome is not None
        assert outcome.outcome_type == OutcomeType.CANCELLED.value
        assert outcome.amount_recovered == 0.0

        # Verify opportunity state
        state = execution_service.get_opportunity_state("opp_003")
        assert state == OpportunityState.CANCELLED.value

    def test_expired_event(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 7: payment_link.expired creates EXPIRED outcome."""
        # Create execution
        payment_link_id = "plink_test_004"
        reference_id = "RAY-opp-004"
        execution = create_mock_execution(
            execution_service, "opp_004", payment_link_id, reference_id
        )

        # Create webhook payload
        payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_EXPIRED.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
        )
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        # Process webhook
        result = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )

        assert result["success"] is True

        # Verify outcome
        outcome = webhook_handler.get_outcome_by_opportunity("opp_004")
        assert outcome is not None
        assert outcome.outcome_type == OutcomeType.EXPIRED.value
        assert outcome.amount_recovered == 0.0

        # Verify opportunity state
        state = execution_service.get_opportunity_state("opp_004")
        assert state == OpportunityState.EXPIRED.value


class TestWebhookIdempotency:
    """Test webhook idempotency."""

    def test_duplicate_event_ignored(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 8: Duplicate event is detected and ignored."""
        # Create execution
        payment_link_id = "plink_test_005"
        reference_id = "RAY-opp-005"
        execution = create_mock_execution(
            execution_service, "opp_005", payment_link_id, reference_id
        )

        # Create webhook payload
        payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_PAID.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            payment_id="pay_test_005",
        )
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        # Process first time
        result1 = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )
        assert result1["success"] is True

        # Process second time (duplicate)
        result2 = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )
        assert result2["success"] is True
        assert result2["status"] == "duplicate"

        # Only one outcome should exist
        outcomes = [
            o for o in webhook_handler.recovery_outcomes.values()
            if o.opportunity_id == "opp_005"
        ]
        assert len(outcomes) == 1


class TestStaleEventProtection:
    """Test stale event protection."""

    def test_expired_after_recovered_ignored(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 9: Expired event after RECOVERED is ignored."""
        # Create execution
        payment_link_id = "plink_test_006"
        reference_id = "RAY-opp-006"
        execution = create_mock_execution(
            execution_service, "opp_006", payment_link_id, reference_id
        )

        # Process paid event first
        paid_payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_PAID.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            payment_id="pay_test_006",
        )
        paid_bytes, paid_signature = sign_payload(paid_payload, webhook_secret)

        result_paid = webhook_handler.process_webhook(
            raw_body=paid_bytes,
            signature=paid_signature,
            payload=paid_payload,
        )
        assert result_paid["success"] is True

        # Verify RECOVERED state
        state = execution_service.get_opportunity_state("opp_006")
        assert state == OpportunityState.RECOVERED.value

        # Process expired event (stale) - use different event_id
        expired_payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_EXPIRED.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            event_id="evt_expired_late_001",
        )
        expired_bytes, expired_signature = sign_payload(expired_payload, webhook_secret)

        result_expired = webhook_handler.process_webhook(
            raw_body=expired_bytes,
            signature=expired_signature,
            payload=expired_payload,
        )
        assert result_expired["success"] is True

        # State should still be RECOVERED (not downgraded to EXPIRED)
        state = execution_service.get_opportunity_state("opp_006")
        assert state == OpportunityState.RECOVERED.value

        # Should still have only one outcome (RECOVERED)
        outcome = webhook_handler.get_outcome_by_opportunity("opp_006")
        assert outcome.outcome_type == OutcomeType.RECOVERED.value

    def test_cancelled_after_recovered_ignored(
        self, webhook_handler, execution_service, webhook_secret
    ):
        """Test 10: Cancelled event after RECOVERED is ignored."""
        # Create execution
        payment_link_id = "plink_test_007"
        reference_id = "RAY-opp-007"
        execution = create_mock_execution(
            execution_service, "opp_007", payment_link_id, reference_id
        )

        # Process paid event first
        paid_payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_PAID.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            payment_id="pay_test_007",
        )
        paid_bytes, paid_signature = sign_payload(paid_payload, webhook_secret)

        result_paid = webhook_handler.process_webhook(
            raw_body=paid_bytes,
            signature=paid_signature,
            payload=paid_payload,
        )
        assert result_paid["success"] is True

        # Process cancelled event (stale) - use different event_id
        cancelled_payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_CANCELLED.value,
            payment_link_id=payment_link_id,
            reference_id=reference_id,
            event_id="evt_cancelled_late_001",
        )
        cancelled_bytes, cancelled_signature = sign_payload(cancelled_payload, webhook_secret)

        result_cancelled = webhook_handler.process_webhook(
            raw_body=cancelled_bytes,
            signature=cancelled_signature,
            payload=cancelled_payload,
        )
        assert result_cancelled["success"] is True

        # State should still be RECOVERED
        state = execution_service.get_opportunity_state("opp_007")
        assert state == OpportunityState.RECOVERED.value


class TestWebhookSecurity:
    """Test webhook security."""

    def test_missing_secret_rejected(
        self, execution_service
    ):
        """Test 11: Missing webhook secret rejected."""
        webhook_handler = WebhookHandler(
            execution_service=execution_service,
            webhook_secret="",
        )

        payload = {"event": "test"}
        payload_bytes = json.dumps(payload).encode()

        result = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature="test_signature",
            payload=payload,
        )

        assert result["success"] is False
        assert "secret not configured" in result["error"]

    def test_unmatched_execution_rejected(
        self, webhook_handler, webhook_secret
    ):
        """Test 12: Unmatched Payment Link rejected."""
        # Create webhook for non-existent execution
        payload = create_webhook_payload(
            event_type=WebhookEventType.PAYMENT_LINK_PAID.value,
            payment_link_id="plink_nonexistent",
            reference_id="RAY-nonexistent",
        )
        payload_bytes, signature = sign_payload(payload, webhook_secret)

        result = webhook_handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )

        assert result["success"] is False
        assert "Execution not found" in result["error"]
