"""
Integration tests for restart safety.

Proves that executions and webhooks survive process restarts.
"""

import pytest
import json
import hmac
import hashlib
import sys
import os
from datetime import datetime

sys.path.insert(0, '/Users/soumaysinghchauhan/Ray')
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray/services/api')

from execution.service_persistent import PersistentExecutionService
from execution.webhooks_persistent import PersistentWebhookHandler
from execution.providers import MockPaymentLinkExecutor
from policy.types import PolicyDecision, PolicyDecisionType
from database.session import SessionLocal, engine, init_db
from database.models import (
    ExecutionAttemptExtended,
    WebhookEventExtended,
    RecoveryOutcomeExtended,
    ContactCount,
)
from sqlalchemy.orm import Session


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Initialize database tables
    init_db()

    # Create session
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()

    # Drop all data (reset for next test)
    session = SessionLocal()
    session.query(RecoveryOutcomeExtended).delete()
    session.query(WebhookEventExtended).delete()
    session.query(ExecutionAttemptExtended).delete()
    session.query(ContactCount).delete()
    session.commit()
    session.close()


def test_execution_survives_restart(db_session):
    """
    Test that execution record survives process restart.

    Flow:
    1. Create execution and persist to database
    2. Drop service instance (simulate restart)
    3. Create new service instance
    4. Verify execution can be loaded from database
    """
    # Phase 1: Create execution
    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, db_session)

    policy_decision = PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id="test_restart_001",
        action_type="create_payment_link",
        policy_version="v1.0",
        evaluated_at=datetime.utcnow().isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )

    opportunity = {
        "merchant_id": "merchant_restart_001",
        "customer_id": "customer_restart_001",
        "amount": 100.0,
        "currency": "INR",
    }

    result1 = service1.execute_allowed_action(policy_decision, opportunity, simulated_day=1)

    assert result1.success is True
    execution_id = result1.execution_id
    payment_link_id = result1.razorpay_payment_link_id
    reference_id = result1.reference_id

    # Phase 2: Simulate restart (drop service instance)
    del service1

    # Phase 3: Create new service instance (simulates restart)
    service2 = PersistentExecutionService(executor, db_session)

    # Phase 4: Verify execution can be loaded
    execution_loaded = service2.get_execution(execution_id)
    assert execution_loaded is not None
    assert execution_loaded.execution_id == execution_id
    assert execution_loaded.opportunity_id == "test_restart_001"
    assert execution_loaded.razorpay_payment_link_id == payment_link_id
    assert execution_loaded.reference_id == reference_id

    # Phase 5: Verify lookup by payment_link_id
    execution_by_link = service2.get_execution_by_payment_link_id(payment_link_id)
    assert execution_by_link is not None
    assert execution_by_link.execution_id == execution_id

    # Phase 6: Verify lookup by reference_id
    execution_by_ref = service2.get_execution_by_reference_id(reference_id)
    assert execution_by_ref is not None
    assert execution_by_ref.execution_id == execution_id


def test_webhook_resolves_after_restart(db_session):
    """
    Test that webhook can resolve execution after process restart.

    Flow:
    1. Create/persist execution
    2. Restart service
    3. Send webhook
    4. Verify execution resolved from database
    5. Verify RecoveryOutcome created
    """
    # Phase 1: Create execution
    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, db_session)

    policy_decision = PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id="test_webhook_restart_001",
        action_type="create_payment_link",
        policy_version="v1.0",
        evaluated_at=datetime.utcnow().isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )

    opportunity = {
        "merchant_id": "merchant_webhook_001",
        "customer_id": "customer_webhook_001",
        "amount": 100.0,
        "currency": "INR",
    }

    result = service1.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
    assert result.success is True

    payment_link_id = result.razorpay_payment_link_id
    reference_id = result.reference_id

    # Phase 2: Simulate restart (drop instances)
    del service1

    # Phase 3: Create new service instances (simulates restart)
    service2 = PersistentExecutionService(executor, db_session)
    webhook_secret = "test_webhook_secret_restart"
    handler = PersistentWebhookHandler(service2, webhook_secret, db_session)

    # Phase 4: Send webhook
    payload = {
        "id": "evt_restart_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": payment_link_id,
                    "reference_id": reference_id,
                    "amount": 10000,
                    "amount_paid": 10000,
                    "payment_id": "pay_restart_001",
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

    # Phase 5: Process webhook
    result = handler.process_webhook(
        raw_body=payload_bytes,
        signature=signature,
        payload=payload,
    )

    # Phase 6: Verify webhook processed successfully
    assert result["success"] is True
    assert result["event_type"] == "payment_link.paid"
    assert result["opportunity_id"] == "test_webhook_restart_001"

    # Phase 7: Verify RecoveryOutcome created in database
    outcome = handler.get_outcome_by_opportunity("test_webhook_restart_001")
    assert outcome is not None
    assert outcome.outcome_type.value == "RECOVERED"
    assert outcome.amount_recovered == 100.0


def test_idempotency_survives_restart(db_session):
    """
    Test that idempotency works across restarts.

    Flow:
    1. Create execution
    2. Restart service
    3. Try to create same execution again
    4. Verify original execution returned (not duplicated)
    """
    # Phase 1: Create execution
    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, db_session)

    policy_decision = PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id="test_idempotency_001",
        action_type="create_payment_link",
        policy_version="v1.0",
        evaluated_at=datetime.utcnow().isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )

    opportunity = {
        "merchant_id": "merchant_idem_001",
        "customer_id": "customer_idem_001",
        "amount": 100.0,
        "currency": "INR",
    }

    result1 = service1.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
    assert result1.success is True
    original_execution_id = result1.execution_id

    # Phase 2: Restart service
    del service1

    # Phase 3: Create new service and try duplicate execution
    service2 = PersistentExecutionService(executor, db_session)
    result2 = service2.execute_allowed_action(policy_decision, opportunity, simulated_day=1)

    # Phase 4: Verify same execution returned (idempotency)
    assert result2.success is True
    assert result2.execution_id == original_execution_id

    # Phase 5: Verify only one execution in database
    executions = db_session.query(ExecutionAttemptExtended).filter(
        ExecutionAttemptExtended.opportunity_id == "test_idempotency_001"
    ).all()
    assert len(executions) == 1


def test_duplicate_webhook_after_restart(db_session):
    """
    Test that duplicate webhook detection works after restart.

    Flow:
    1. Process webhook
    2. Restart service
    3. Send same webhook again
    4. Verify detected as duplicate
    """
    # Phase 1: Create execution
    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, db_session)

    policy_decision = PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id="test_dup_webhook_001",
        action_type="create_payment_link",
        policy_version="v1.0",
        evaluated_at=datetime.utcnow().isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )

    opportunity = {
        "merchant_id": "merchant_dup_001",
        "customer_id": "customer_dup_001",
        "amount": 100.0,
        "currency": "INR",
    }

    result = service1.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
    payment_link_id = result.razorpay_payment_link_id

    # Phase 2: Process first webhook
    webhook_secret = "test_webhook_secret_dup"
    handler1 = PersistentWebhookHandler(service1, webhook_secret, db_session)

    payload = {
        "id": "evt_dup_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": payment_link_id,
                    "amount": 10000,
                    "amount_paid": 10000,
                    "payment_id": "pay_dup_001",
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

    result1 = handler1.process_webhook(payload_bytes, signature, payload)
    assert result1["success"] is True

    # Phase 3: Restart services
    del service1
    del handler1

    # Phase 4: Create new instances
    service2 = PersistentExecutionService(executor, db_session)
    handler2 = PersistentWebhookHandler(service2, webhook_secret, db_session)

    # Phase 5: Send same webhook again
    result2 = handler2.process_webhook(payload_bytes, signature, payload)

    # Phase 6: Verify detected as duplicate
    assert result2["success"] is True
    assert result2["status"] == "duplicate"

    # Phase 7: Verify only one outcome in database
    outcomes = db_session.query(RecoveryOutcomeExtended).filter(
        RecoveryOutcomeExtended.opportunity_id == "test_dup_webhook_001"
    ).all()
    assert len(outcomes) == 1


def test_contact_count_persists_after_restart(db_session):
    """
    Test that contact counts persist after restart.

    Flow:
    1. Create execution (increments contact count)
    2. Restart service
    3. Check contact count from new service
    4. Verify count correct
    """
    # Phase 1: Create execution
    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, db_session)

    policy_decision = PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id="test_contact_001",
        action_type="create_payment_link",
        policy_version="v1.0",
        evaluated_at=datetime.utcnow().isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )

    opportunity = {
        "merchant_id": "merchant_contact_001",
        "customer_id": "customer_contact_001",
        "amount": 100.0,
        "currency": "INR",
    }

    result = service1.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
    assert result.success is True

    # Phase 2: Restart service
    del service1

    # Phase 3: Create new service
    service2 = PersistentExecutionService(executor, db_session)

    # Phase 4: Verify contact count persisted
    count = service2.get_contact_count("merchant_contact_001", "customer_contact_001", 1)
    assert count == 1
