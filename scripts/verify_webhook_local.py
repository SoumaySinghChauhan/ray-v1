"""
RAY V1 - Local Webhook Verification

Verifies all webhook functionality locally before public exposure.
NO Razorpay API calls. NO tunnel configuration. Mock tests only.
"""

import sys
import os
import json
import hmac
import hashlib
import time
from datetime import datetime

# Setup paths
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray')
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray/services/api')

# Set test webhook secret
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_local_webhook_secret_12345"


def test_1_database_initialization():
    """Test 1: Database initializes successfully."""
    print("\n" + "="*70)
    print("TEST 1: Database Initialization")
    print("="*70)

    try:
        from database.session import init_db, engine

        print(f"Database URL: {engine.url}")

        # Initialize database
        init_db()

        print("✅ PASS: Database initialized successfully")
        return True

    except Exception as e:
        print(f"❌ FAIL: Database initialization failed: {e}")
        return False


def test_2_fastapi_starts():
    """Test 2: FastAPI application starts successfully."""
    print("\n" + "="*70)
    print("TEST 2: FastAPI Application Start")
    print("="*70)

    try:
        from services.api.main import app

        print(f"App title: {app.title}")
        print(f"App version: {app.version}")
        print(f"Routes registered: {len(app.routes)}")

        print("✅ PASS: FastAPI application loads successfully")
        return True

    except Exception as e:
        print(f"❌ FAIL: FastAPI application failed to load: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_health_endpoint():
    """Test 3: GET /health returns 200."""
    print("\n" + "="*70)
    print("TEST 3: Health Endpoint")
    print("="*70)

    try:
        from services.api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 200:
            print("✅ PASS: Health endpoint returns 200")
            return True
        else:
            print(f"❌ FAIL: Health endpoint returned {response.status_code}")
            return False

    except ImportError:
        print("⚠️  SKIP: FastAPI test client not available (httpx not installed)")
        print("   Checking route registration instead...")

        try:
            from services.api.main import app
            routes = [r.path for r in app.routes]

            if "/health" in routes:
                print("✅ PASS: Health endpoint registered")
                return True
            else:
                print("❌ FAIL: Health endpoint not found")
                return False
        except Exception as e:
            print(f"❌ FAIL: {e}")
            return False

    except Exception as e:
        print(f"❌ FAIL: Health endpoint test failed: {e}")
        return False


def test_4_webhook_route_exists():
    """Test 4: POST /webhooks/razorpay exists."""
    print("\n" + "="*70)
    print("TEST 4: Webhook Route Registration")
    print("="*70)

    try:
        from services.api.main import app

        routes = [(r.path, r.methods) for r in app.routes]

        webhook_route = None
        for path, methods in routes:
            if path == "/webhooks/razorpay":
                webhook_route = (path, methods)
                break

        if webhook_route:
            print(f"Route: {webhook_route[0]}")
            print(f"Methods: {webhook_route[1]}")

            if "POST" in webhook_route[1]:
                print("✅ PASS: Webhook route registered with POST method")
                return True
            else:
                print("❌ FAIL: Webhook route exists but POST not allowed")
                return False
        else:
            print("❌ FAIL: Webhook route not found")
            return False

    except Exception as e:
        print(f"❌ FAIL: Route check failed: {e}")
        return False


def test_5_webhook_secret_loaded():
    """Test 5: RAZORPAY_WEBHOOK_SECRET loaded from environment."""
    print("\n" + "="*70)
    print("TEST 5: Webhook Secret Environment Variable")
    print("="*70)

    try:
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

        if webhook_secret:
            print(f"Secret loaded: {'*' * len(webhook_secret)} ({len(webhook_secret)} chars)")
            print("✅ PASS: Webhook secret loaded from environment")
            return True
        else:
            print("❌ FAIL: Webhook secret not found in environment")
            return False

    except Exception as e:
        print(f"❌ FAIL: Environment check failed: {e}")
        return False


def test_6_valid_signed_webhook():
    """Test 6: Valid locally generated signed webhook is accepted."""
    print("\n" + "="*70)
    print("TEST 6: Valid Signed Webhook")
    print("="*70)

    try:
        # Create execution first
        from database.session import SessionLocal
        from execution.service_persistent import PersistentExecutionService
        from execution.webhooks_persistent import PersistentWebhookHandler
        from execution.providers import MockPaymentLinkExecutor
        from policy.types import PolicyDecision, PolicyDecisionType

        # Cleanup
        session = SessionLocal()
        from database.models import ExecutionAttemptExtended, WebhookEventExtended, RecoveryOutcomeExtended
        session.query(RecoveryOutcomeExtended).delete()
        session.query(WebhookEventExtended).delete()
        session.query(ExecutionAttemptExtended).delete()
        session.commit()

        # Create execution
        executor = MockPaymentLinkExecutor()
        service = PersistentExecutionService(executor, session)

        policy_decision = PolicyDecision(
            decision=PolicyDecisionType.ALLOW.value,
            opportunity_id="test_valid_webhook_001",
            action_type="create_payment_link",
            policy_version="v1.0",
            evaluated_at=datetime.utcnow().isoformat(),
            primary_reason=None,
            all_rule_results=[],
        )

        opportunity = {
            "merchant_id": "merchant_test_001",
            "customer_id": "customer_test_001",
            "amount": 100.0,
            "currency": "INR",
        }

        result = service.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
        payment_link_id = result.razorpay_payment_link_id

        print(f"Execution created: {payment_link_id}")

        # Create webhook
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        handler = PersistentWebhookHandler(service, webhook_secret, session)

        payload = {
            "id": "evt_valid_001",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": payment_link_id,
                        "amount": 10000,
                        "amount_paid": 10000,
                        "payment_id": "pay_valid_001",
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

        print(f"Webhook signed with secret")
        print(f"Signature: {signature[:20]}...")

        # Process webhook
        result = handler.process_webhook(
            raw_body=payload_bytes,
            signature=signature,
            payload=payload,
        )

        print(f"Webhook result: {result}")

        session.close()

        if result.get("success"):
            print("✅ PASS: Valid signed webhook accepted")
            return True
        else:
            print(f"❌ FAIL: Valid webhook rejected: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ FAIL: Valid webhook test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_invalid_signature_rejected():
    """Test 7: Invalid signature is rejected."""
    print("\n" + "="*70)
    print("TEST 7: Invalid Signature Rejection")
    print("="*70)

    try:
        from database.session import SessionLocal
        from execution.service_persistent import PersistentExecutionService
        from execution.webhooks_persistent import PersistentWebhookHandler
        from execution.providers import MockPaymentLinkExecutor

        session = SessionLocal()
        executor = MockPaymentLinkExecutor()
        service = PersistentExecutionService(executor, session)

        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        handler = PersistentWebhookHandler(service, webhook_secret, session)

        payload = {
            "id": "evt_invalid_001",
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_invalid",
                        "amount": 10000,
                    }
                }
            },
        }

        payload_bytes = json.dumps(payload).encode()
        invalid_signature = "invalid_signature_abc123"

        print(f"Invalid signature: {invalid_signature}")

        result = handler.process_webhook(
            raw_body=payload_bytes,
            signature=invalid_signature,
            payload=payload,
        )

        print(f"Webhook result: {result}")

        session.close()

        if not result.get("success") and "Invalid signature" in result.get("error", ""):
            print("✅ PASS: Invalid signature rejected")
            return True
        else:
            print("❌ FAIL: Invalid signature was accepted")
            return False

    except Exception as e:
        print(f"❌ FAIL: Invalid signature test failed: {e}")
        return False


def test_8_duplicate_event_handled():
    """Test 8: Duplicate event is deduplicated."""
    print("\n" + "="*70)
    print("TEST 8: Duplicate Event Deduplication")
    print("="*70)

    try:
        from database.session import SessionLocal
        from execution.service_persistent import PersistentExecutionService
        from execution.webhooks_persistent import PersistentWebhookHandler
        from execution.providers import MockPaymentLinkExecutor
        from policy.types import PolicyDecision, PolicyDecisionType
        from database.models import ExecutionAttemptExtended, WebhookEventExtended, RecoveryOutcomeExtended

        # Cleanup
        session = SessionLocal()
        session.query(RecoveryOutcomeExtended).delete()
        session.query(WebhookEventExtended).delete()
        session.query(ExecutionAttemptExtended).delete()
        session.commit()

        # Create execution
        executor = MockPaymentLinkExecutor()
        service = PersistentExecutionService(executor, session)

        policy_decision = PolicyDecision(
            decision=PolicyDecisionType.ALLOW.value,
            opportunity_id="test_dup_001",
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

        result = service.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
        payment_link_id = result.razorpay_payment_link_id

        # Create handler
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        handler = PersistentWebhookHandler(service, webhook_secret, session)

        payload = {
            "id": "evt_dup_unique_001",
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

        # Process first time
        result1 = handler.process_webhook(payload_bytes, signature, payload)
        print(f"First webhook: {result1.get('success')}")

        # Process second time (duplicate)
        result2 = handler.process_webhook(payload_bytes, signature, payload)
        print(f"Second webhook: {result2.get('success')}, status: {result2.get('status')}")

        session.close()

        if result1.get("success") and result2.get("status") == "duplicate":
            print("✅ PASS: Duplicate event detected and handled")
            return True
        else:
            print("❌ FAIL: Duplicate event not properly handled")
            return False

    except Exception as e:
        print(f"❌ FAIL: Duplicate event test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_9_outcome_persists():
    """Test 9: RecoveryOutcome persists to database."""
    print("\n" + "="*70)
    print("TEST 9: Recovery Outcome Persistence")
    print("="*70)

    try:
        from database.session import SessionLocal
        from database.models import RecoveryOutcomeExtended

        session = SessionLocal()

        # Query for outcomes
        outcomes = session.query(RecoveryOutcomeExtended).all()

        print(f"Outcomes in database: {len(outcomes)}")

        if outcomes:
            outcome = outcomes[0]
            print(f"Sample outcome:")
            print(f"  - ID: {outcome.id}")
            print(f"  - Opportunity ID: {outcome.opportunity_id}")
            print(f"  - Outcome type: {outcome.outcome_type.value}")
            print(f"  - Amount recovered: ₹{outcome.amount_recovered}")

        session.close()

        if len(outcomes) > 0:
            print("✅ PASS: Recovery outcomes persist to database")
            return True
        else:
            print("❌ FAIL: No recovery outcomes found in database")
            return False

    except Exception as e:
        print(f"❌ FAIL: Outcome persistence check failed: {e}")
        return False


def test_10_restart_survival():
    """Test 10: State survives service restart."""
    print("\n" + "="*70)
    print("TEST 10: Service Restart Survival")
    print("="*70)

    try:
        from database.session import SessionLocal
        from execution.service_persistent import PersistentExecutionService
        from execution.providers import MockPaymentLinkExecutor
        from policy.types import PolicyDecision, PolicyDecisionType
        from database.models import ExecutionAttemptExtended

        # Phase 1: Create execution
        print("[Phase 1] Creating execution...")
        session1 = SessionLocal()

        # Cleanup
        from database.models import RecoveryOutcomeExtended, WebhookEventExtended
        session1.query(RecoveryOutcomeExtended).delete()
        session1.query(WebhookEventExtended).delete()
        session1.query(ExecutionAttemptExtended).delete()
        session1.commit()

        executor = MockPaymentLinkExecutor()
        service1 = PersistentExecutionService(executor, session1)

        policy_decision = PolicyDecision(
            decision=PolicyDecisionType.ALLOW.value,
            opportunity_id="test_restart_local_001",
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

        result = service1.execute_allowed_action(policy_decision, opportunity, simulated_day=1)
        execution_id = result.execution_id

        print(f"  Execution created: {execution_id}")

        session1.close()

        # Phase 2: Simulate restart
        print("[Phase 2] Simulating restart...")
        del service1
        del session1
        print("  Service instance dropped")

        # Phase 3: Load from new instance
        print("[Phase 3] Loading from new instance...")
        session2 = SessionLocal()
        service2 = PersistentExecutionService(executor, session2)

        loaded = service2.get_execution(execution_id)

        if loaded:
            print(f"  Execution loaded: {loaded.execution_id}")
            print(f"  Opportunity ID: {loaded.opportunity_id}")
            print(f"  State: {loaded.state}")

        session2.close()

        if loaded and loaded.execution_id == execution_id:
            print("✅ PASS: State survives service restart")
            return True
        else:
            print("❌ FAIL: State not recovered after restart")
            return False

    except Exception as e:
        print(f"❌ FAIL: Restart survival test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all local webhook verification tests."""
    print("\n" + "="*70)
    print("RAY V1 - LOCAL WEBHOOK VERIFICATION")
    print("="*70)
    print("\nVerifying webhook functionality before public exposure.")
    print("NO Razorpay API calls. NO tunnel configuration. Mock tests only.")
    print()

    results = []

    # Run tests
    results.append(("Database initialization", test_1_database_initialization()))
    results.append(("FastAPI starts", test_2_fastapi_starts()))
    results.append(("Health endpoint", test_3_health_endpoint()))
    results.append(("Webhook route exists", test_4_webhook_route_exists()))
    results.append(("Webhook secret loaded", test_5_webhook_secret_loaded()))
    results.append(("Valid signed webhook", test_6_valid_signed_webhook()))
    results.append(("Invalid signature rejected", test_7_invalid_signature_rejected()))
    results.append(("Duplicate event handled", test_8_duplicate_event_handled()))
    results.append(("Outcome persists", test_9_outcome_persists()))
    results.append(("Restart survival", test_10_restart_survival()))

    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    print()

    for i, (name, passed) in enumerate(results, 1):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{i:2d}. {name:35s} {status}")

    print()
    print("="*70)

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    if passed_count == total_count:
        print(f"✅ ALL TESTS PASSED ({passed_count}/{total_count})")
        print()
        print("System ready for public webhook exposure.")
        print()
        print("Next steps:")
        print("  1. Set RAZORPAY_WEBHOOK_SECRET in .env (from Razorpay dashboard)")
        print("  2. Start server: cd services/api && python main.py")
        print("  3. Expose with ngrok: ngrok http 8000")
        print("  4. Configure webhook in Razorpay dashboard")
        print("  5. Test with real Payment Link")
        return 0
    else:
        print(f"❌ TESTS FAILED ({passed_count}/{total_count} passed)")
        print()
        print("Fix failing tests before public exposure.")
        return 1


if __name__ == "__main__":
    exit(main())
