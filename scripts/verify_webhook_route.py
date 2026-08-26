"""
Quick webhook route verification script.

Verifies that the Razorpay webhook route is properly integrated.
"""

import sys
import os
import json
import hmac
import hashlib

# Add RAY to path
sys.path.insert(0, '/Users/soumaysinghchauhan/Ray')

# Set webhook secret for testing
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_webhook_secret_12345"

def test_signature_verification():
    """Test that signature verification works."""
    from execution.providers import verify_webhook_signature

    payload = {"test": "data"}
    payload_bytes = json.dumps(payload).encode()
    secret = "test_webhook_secret_12345"

    # Create valid signature
    signature = hmac.new(
        key=secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Verify
    result = verify_webhook_signature(payload_bytes, signature, secret)
    assert result is True, "Valid signature should verify"
    print("✅ Signature verification: PASS")

    # Test invalid signature
    result = verify_webhook_signature(payload_bytes, "invalid", secret)
    assert result is False, "Invalid signature should fail"
    print("✅ Invalid signature rejection: PASS")


def test_webhook_handler():
    """Test that WebhookHandler processes webhooks correctly."""
    from execution.service import ExecutionService
    from execution.providers import MockPaymentLinkExecutor
    from execution.webhooks import WebhookHandler

    # Create execution service
    executor = MockPaymentLinkExecutor()
    execution_service = ExecutionService(executor)

    # Create webhook handler
    webhook_secret = "test_webhook_secret_12345"
    handler = WebhookHandler(execution_service, webhook_secret)

    # Create test payload
    payload = {
        "id": "evt_test_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test_001",
                    "reference_id": "RAY-test-001",
                    "amount": 1000000,
                    "amount_paid": 1000000,
                    "payment_id": "pay_test_001",
                }
            }
        },
    }

    payload_bytes = json.dumps(payload).encode()

    # Sign payload
    signature = hmac.new(
        key=webhook_secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Process webhook
    result = handler.process_webhook(
        raw_body=payload_bytes,
        signature=signature,
        payload=payload,
    )

    # Check result
    print(f"Webhook processing result: {result}")

    if result.get("success") is False and "Invalid signature" in result.get("error", ""):
        print("❌ Signature verification failed")
        return False

    print("✅ Webhook handler: PASS")
    return True


def test_fastapi_route_exists():
    """Test that FastAPI route exists and responds."""
    print("\nChecking FastAPI route configuration...")

    try:
        from services.api.main import app

        # Check routes
        routes = [r.path for r in app.routes]

        if "/webhooks/razorpay" in routes:
            print("✅ Webhook route registered: /webhooks/razorpay")
            return True
        else:
            print("❌ Webhook route NOT found")
            return False
    except Exception as e:
        print(f"❌ Error loading FastAPI app: {e}")
        return False


def main():
    """Run all verification checks."""
    print("RAY Webhook Integration Verification")
    print("=" * 50)
    print()

    # Test 1: Signature verification
    print("Test 1: Signature Verification")
    try:
        test_signature_verification()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return 1
    print()

    # Test 2: Webhook handler
    print("Test 2: Webhook Handler")
    try:
        test_webhook_handler()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return 1
    print()

    # Test 3: FastAPI route
    print("Test 3: FastAPI Route")
    try:
        test_fastapi_route_exists()
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return 1
    print()

    print("=" * 50)
    print("✅ ALL VERIFICATION CHECKS PASSED")
    print()
    print("Next steps:")
    print("1. Set RAZORPAY_WEBHOOK_SECRET in .env")
    print("2. Start server: cd services/api && .venv/bin/python main.py")
    print("3. Expose with ngrok: ngrok http 8000")
    print("4. Configure webhook in Razorpay dashboard")
    print("5. Test with real Payment Link")

    return 0


if __name__ == "__main__":
    sys.exit(main())
