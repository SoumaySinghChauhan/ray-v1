"""
Integration tests for execution persistence across creation and webhook processing.

REGRESSION TESTS: These tests ensure that Payment Link creation and webhook
processing use the same persistent database, preventing "Execution not found" errors.
"""

import pytest
import json
import hmac
import hashlib
from decimal import Decimal
from datetime import datetime, timezone


@pytest.fixture
def db_session():
    """Create a clean database session for testing."""
    from database.session import SessionLocal, init_db

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    yield db

    # Cleanup
    db.close()


@pytest.fixture
def mock_executor():
    """Mock Payment Link executor for testing."""
    from execution.providers import MockPaymentLinkExecutor
    return MockPaymentLinkExecutor()


@pytest.fixture
def test_opportunity():
    """Test opportunity data."""
    return {
        "opportunity_id": "test_opp_persistence_001",
        "merchant_id": "test_merchant",
        "customer_id": "test_customer",
        "amount": Decimal("100.00"),
        "currency": "INR",
        "customer_contact": "+919876543210",
        "customer_email": "test@example.com",
        "customer_name": "Test Customer",
    }


@pytest.fixture
def test_policy_decision(test_opportunity):
    """Test policy decision."""
    from policy.types import PolicyDecision, PolicyDecisionType

    return PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id=test_opportunity["opportunity_id"],
        action_type="create_payment_link",
        policy_version="1.0.0",
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )


def test_persistent_service_creates_database_record(
    db_session, mock_executor, test_policy_decision, test_opportunity
):
    """
    TEST 1: Payment Link creation uses PersistentExecutionService.

    Regression test: Ensures execution records are persisted to database.
    """
    from execution.service_persistent import PersistentExecutionService
    from database.models import ExecutionAttemptExtended

    # Create persistent service
    service = PersistentExecutionService(executor=mock_executor, db_session=db_session)

    # Execute action
    result = service.execute_allowed_action(
        policy_decision=test_policy_decision,
        opportunity=test_opportunity,
        simulated_day=1,
    )

    # Verify success
    assert result.success
    assert result.execution_id is not None
    assert result.razorpay_payment_link_id is not None

    # Verify database record exists
    execution = (
        db_session.query(ExecutionAttemptExtended)
        .filter(ExecutionAttemptExtended.id == result.execution_id)
        .first()
    )

    assert execution is not None
    assert execution.opportunity_id == test_opportunity["opportunity_id"]
    assert execution.razorpay_payment_link_id == result.razorpay_payment_link_id
    assert execution.reference_id == result.reference_id


def test_webhook_resolves_persisted_execution(
    db_session, mock_executor, test_policy_decision, test_opportunity, monkeypatch
):
    """
    TEST 2: Webhook finds execution created by PersistentExecutionService.

    Regression test: Creation and webhook use the same database.
    """
    from execution.service_persistent import PersistentExecutionService
    from execution.webhooks_persistent import PersistentWebhookHandler

    # Create persistent service
    service = PersistentExecutionService(executor=mock_executor, db_session=db_session)

    # Execute action
    result = service.execute_allowed_action(
        policy_decision=test_policy_decision,
        opportunity=test_opportunity,
        simulated_day=1,
    )

    assert result.success

    # Create webhook payload
    webhook_secret = "test_webhook_secret"
    payload = {
        "id": "evt_persistence_test_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": result.razorpay_payment_link_id,
                    "reference_id": result.reference_id,
                    "status": "paid",
                    "amount": 10000,
                    "amount_paid": 10000,
                    "currency": "INR",
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_persistence_test_001",
                    "amount": 10000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        key=webhook_secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Create webhook handler
    handler = PersistentWebhookHandler(service, webhook_secret, db_session)

    # Process webhook
    webhook_result = handler.process_webhook(
        raw_body=payload_bytes,
        signature=signature,
        payload=payload,
    )

    # Verify webhook found execution
    assert webhook_result["success"] is True
    assert "Execution not found" not in webhook_result.get("error", "")


def test_execution_survives_process_restart(
    db_session, mock_executor, test_policy_decision, test_opportunity
):
    """
    TEST 3: Execution record survives process restart.

    Regression test: Database persistence works across sessions.
    """
    from execution.service_persistent import PersistentExecutionService
    from database.models import ExecutionAttemptExtended
    from database.session import SessionLocal

    # Create service and execute
    service = PersistentExecutionService(executor=mock_executor, db_session=db_session)
    result = service.execute_allowed_action(
        policy_decision=test_policy_decision,
        opportunity=test_opportunity,
        simulated_day=1,
    )

    assert result.success
    execution_id = result.execution_id
    payment_link_id = result.razorpay_payment_link_id

    # Close session (simulates process restart)
    db_session.close()

    # Create NEW session (simulates new process)
    new_db = SessionLocal()

    try:
        # Verify execution exists in new session
        execution = (
            new_db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.id == execution_id)
            .first()
        )

        assert execution is not None
        assert execution.razorpay_payment_link_id == payment_link_id

        # Verify lookup by payment_link_id works
        by_plink = (
            new_db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.razorpay_payment_link_id == payment_link_id)
            .first()
        )

        assert by_plink is not None
        assert by_plink.id == execution_id

    finally:
        new_db.close()


def test_duplicate_webhook_remains_idempotent(
    db_session, mock_executor, test_policy_decision, test_opportunity
):
    """
    TEST 4: Duplicate webhooks are idempotent with persisted execution.

    Regression test: Idempotency works across restarts.
    """
    from execution.service_persistent import PersistentExecutionService
    from execution.webhooks_persistent import PersistentWebhookHandler

    # Create execution
    service = PersistentExecutionService(executor=mock_executor, db_session=db_session)
    result = service.execute_allowed_action(
        policy_decision=test_policy_decision,
        opportunity=test_opportunity,
        simulated_day=1,
    )

    assert result.success

    # Create webhook payload
    webhook_secret = "test_webhook_secret"
    payload = {
        "id": "evt_idempotency_test_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": result.razorpay_payment_link_id,
                    "reference_id": result.reference_id,
                    "status": "paid",
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_idempotency_test_001",
                }
            }
        },
    }

    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        key=webhook_secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    handler = PersistentWebhookHandler(service, webhook_secret, db_session)

    # First webhook
    result1 = handler.process_webhook(
        raw_body=payload_bytes,
        signature=signature,
        payload=payload,
    )

    assert result1["success"] is True
    webhook_id_1 = result1["webhook_id"]

    # Second webhook (duplicate)
    result2 = handler.process_webhook(
        raw_body=payload_bytes,
        signature=signature,
        payload=payload,
    )

    # Should be marked as duplicate
    assert result2["success"] is True
    assert result2.get("status") == "duplicate"
    assert "already processed" in result2.get("message", "").lower()


def test_in_memory_service_does_not_persist():
    """
    TEST 5: Verify in-memory service does NOT persist (for comparison).

    This test documents the OLD behavior to prevent regression.
    """
    from execution.service import ExecutionService
    from execution.providers import MockPaymentLinkExecutor
    from policy.types import PolicyDecision, PolicyDecisionType
    from database.session import SessionLocal
    from database.models import ExecutionAttemptExtended

    db = SessionLocal()

    try:
        # Create in-memory service (OLD way)
        executor = MockPaymentLinkExecutor()
        service = ExecutionService(executor=executor)

        policy_decision = PolicyDecision(
            decision=PolicyDecisionType.ALLOW.value,
            opportunity_id="test_opp_in_memory",
            action_type="create_payment_link",
            policy_version="1.0.0",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            primary_reason=None,
            all_rule_results=[],
        )

        opportunity = {
            "opportunity_id": "test_opp_in_memory",
            "merchant_id": "test_merchant",
            "customer_id": "test_customer",
            "amount": Decimal("100.00"),
            "currency": "INR",
        }

        result = service.execute_allowed_action(
            policy_decision=policy_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        assert result.success
        execution_id = result.execution_id

        # Verify NOT in database
        execution = (
            db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.id == execution_id)
            .first()
        )

        # Should be None (not persisted)
        assert execution is None, \
            "In-memory ExecutionService should NOT persist to database"

    finally:
        db.close()
