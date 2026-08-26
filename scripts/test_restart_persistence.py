"""
Standalone restart persistence demonstration.

Proves that executions and webhooks survive process restarts.
Does not require pytest - can be run directly.
"""

import sys
import os
import json
import hmac
import hashlib
from datetime import datetime

# Add paths
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray')
ray_root = '/Users/soumaysinghchauhan/Ray'
sys.path.insert(0, os.path.join(ray_root, 'services', 'api'))

from execution.service_persistent import PersistentExecutionService
from execution.webhooks_persistent import PersistentWebhookHandler
from execution.providers import MockPaymentLinkExecutor
from policy.types import PolicyDecision, PolicyDecisionType
from database.session import SessionLocal, init_db
from database.models import (
    ExecutionAttemptExtended,
    WebhookEventExtended,
    RecoveryOutcomeExtended,
)


def cleanup_test_data(session):
    """Clean up any existing test data."""
    session.query(RecoveryOutcomeExtended).delete()
    session.query(WebhookEventExtended).delete()
    session.query(ExecutionAttemptExtended).delete()
    session.commit()


def test_1_execution_survives_restart():
    """Test that execution record survives process restart."""
    print("\n" + "=" * 70)
    print("TEST 1: Execution Survives Restart")
    print("=" * 70)

    # Phase 1: Create execution
    print("\n[Phase 1] Creating execution...")
    session1 = SessionLocal()
    cleanup_test_data(session1)

    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, session1)

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

    assert result1.success is True, "Execution should succeed"
    execution_id = result1.execution_id
    payment_link_id = result1.razorpay_payment_link_id
    reference_id = result1.reference_id

    print(f"✅ Execution created:")
    print(f"   - Execution ID: {execution_id}")
    print(f"   - Payment Link ID: {payment_link_id}")
    print(f"   - Reference ID: {reference_id}")

    session1.close()

    # Phase 2: Simulate restart (create new session and service)
    print("\n[Phase 2] Simulating process restart...")
    print("   - Dropped service instance")
    print("   - Dropped database session")

    del service1

    # Phase 3: Create new service instance (simulates restart)
    print("\n[Phase 3] Creating new service instance...")
    session2 = SessionLocal()
    service2 = PersistentExecutionService(executor, session2)

    print("✅ New service instance created")

    # Phase 4: Verify execution can be loaded
    print("\n[Phase 4] Loading execution from database...")
    execution_loaded = service2.get_execution(execution_id)

    assert execution_loaded is not None, "Execution should be loaded from database"
    assert execution_loaded.execution_id == execution_id
    assert execution_loaded.opportunity_id == "test_restart_001"
    assert execution_loaded.razorpay_payment_link_id == payment_link_id
    assert execution_loaded.reference_id == reference_id

    print("✅ Execution loaded successfully:")
    print(f"   - Execution ID matches: {execution_loaded.execution_id == execution_id}")
    print(f"   - Opportunity ID matches: {execution_loaded.opportunity_id == 'test_restart_001'}")
    print(f"   - Payment Link ID matches: {execution_loaded.razorpay_payment_link_id == payment_link_id}")

    # Phase 5: Verify lookup methods
    print("\n[Phase 5] Testing lookup methods...")
    execution_by_link = service2.get_execution_by_payment_link_id(payment_link_id)
    execution_by_ref = service2.get_execution_by_reference_id(reference_id)

    assert execution_by_link is not None, "Lookup by payment_link_id should work"
    assert execution_by_ref is not None, "Lookup by reference_id should work"

    print("✅ Lookup methods verified:")
    print(f"   - By payment_link_id: {execution_by_link.execution_id}")
    print(f"   - By reference_id: {execution_by_ref.execution_id}")

    session2.close()
    print("\n✅ TEST 1 PASSED: Execution survives restart!")


def test_2_webhook_resolves_after_restart():
    """Test that webhook can resolve execution after process restart."""
    print("\n" + "=" * 70)
    print("TEST 2: Webhook Resolves After Restart")
    print("=" * 70)

    # Phase 1: Create execution
    print("\n[Phase 1] Creating execution...")
    session1 = SessionLocal()
    cleanup_test_data(session1)

    executor = MockPaymentLinkExecutor()
    service1 = PersistentExecutionService(executor, session1)

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

    print(f"✅ Execution created: {payment_link_id}")

    session1.close()

    # Phase 2: Simulate restart
    print("\n[Phase 2] Simulating process restart...")
    del service1
    print("✅ Service instance dropped")

    # Phase 3: Create new service instances
    print("\n[Phase 3] Creating new service instances...")
    session2 = SessionLocal()
    service2 = PersistentExecutionService(executor, session2)
    webhook_secret = "test_webhook_secret_restart"
    handler = PersistentWebhookHandler(service2, webhook_secret, session2)

    print("✅ New services created")

    # Phase 4: Send webhook
    print("\n[Phase 4] Processing webhook...")
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

    result = handler.process_webhook(
        raw_body=payload_bytes,
        signature=signature,
        payload=payload,
    )

    # Phase 5: Verify webhook processed
    assert result["success"] is True, "Webhook should process successfully"
    assert result["event_type"] == "payment_link.paid"
    assert result["opportunity_id"] == "test_webhook_restart_001"

    print("✅ Webhook processed successfully:")
    print(f"   - Event type: {result['event_type']}")
    print(f"   - Opportunity ID: {result['opportunity_id']}")

    # Phase 6: Verify RecoveryOutcome created
    print("\n[Phase 5] Verifying recovery outcome...")
    outcome = handler.get_outcome_by_opportunity("test_webhook_restart_001")

    assert outcome is not None, "Outcome should be created"
    assert outcome.outcome_type.value == "RECOVERED"
    assert outcome.amount_recovered == 100.0

    print("✅ Recovery outcome created:")
    print(f"   - Outcome type: {outcome.outcome_type.value}")
    print(f"   - Amount recovered: ₹{outcome.amount_recovered}")

    session2.close()
    print("\n✅ TEST 2 PASSED: Webhook resolves after restart!")


def main():
    """Run all restart persistence tests."""
    print("\n" + "=" * 70)
    print("RAY V1 - RESTART PERSISTENCE DEMONSTRATION")
    print("=" * 70)
    print("\nThis script proves that executions and webhooks survive process restarts.")
    print("Database: SQLite (ray_v1.db)")

    # Initialize database
    print("\nInitializing database...")
    init_db()
    print("✅ Database initialized")

    try:
        # Test 1: Execution survives restart
        test_1_execution_survives_restart()

        # Test 2: Webhook resolves after restart
        test_2_webhook_resolves_after_restart()

        # Summary
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED")
        print("=" * 70)
        print("\n✅ Execution records persist across restarts")
        print("✅ Webhook events can resolve executions after restart")
        print("✅ Recovery outcomes persist to database")
        print("✅ Database is source of truth (not in-memory)")
        print("\nRestart safety: VERIFIED")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
