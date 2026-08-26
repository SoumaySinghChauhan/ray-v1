"""
Integration tests for webhook signature verification ordering.

SECURITY REGRESSION TEST: These tests MUST pass to ensure signature
verification happens BEFORE JSON parsing.

If these tests fail, it indicates a security vulnerability where
unauthenticated requests can trigger JSON parsing.
"""

import pytest
import json
import hmac
import hashlib


@pytest.fixture
def webhook_secret():
    """Test webhook secret."""
    return "test_security_webhook_secret"


@pytest.fixture
def client(monkeypatch, webhook_secret):
    """FastAPI test client with webhook secret."""
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", webhook_secret)

    from fastapi.testclient import TestClient
    from services.api.main import app
    return TestClient(app)


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    return hmac.new(
        key=secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


# ============================================================================
# SECURITY TESTS: Signature Verification Order
# ============================================================================


def test_valid_signature_with_valid_json(client, webhook_secret):
    """
    TEST 1: Valid body + valid signature → accepted.

    This is the happy path baseline.
    """
    payload = {
        "id": "evt_security_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_security_001",
                    "reference_id": "RAY-security-001",
                }
            }
        },
    }

    payload_bytes = json.dumps(payload).encode()
    signature = sign_payload(payload_bytes, webhook_secret)

    response = client.post(
        "/webhooks/razorpay",
        content=payload_bytes,
        headers={
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    # May return 400 (execution not found) but signature was verified
    assert response.status_code in [200, 400]

    # Should NOT be "Invalid signature" error
    if response.status_code == 400:
        data = response.json()
        assert "Invalid signature" not in data.get("error", "")


def test_invalid_signature_with_valid_json_rejected_before_parsing(client):
    """
    TEST 2: Valid JSON + invalid signature → rejected BEFORE processing.

    CRITICAL: This proves JSON is NOT parsed when signature is invalid.
    """
    payload = {
        "id": "evt_security_002",
        "event": "payment_link.paid",
        "payload": {"payment_link": {"entity": {"id": "plink_test"}}},
    }

    payload_bytes = json.dumps(payload).encode()
    invalid_signature = "INVALID_SIGNATURE_12345"

    response = client.post(
        "/webhooks/razorpay",
        content=payload_bytes,
        headers={
            "X-Razorpay-Signature": invalid_signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid signature" in data["error"]


def test_malformed_json_with_invalid_signature_returns_invalid_signature(client):
    """
    TEST 3: Malformed JSON + invalid signature → invalid-signature response.

    CRITICAL SECURITY TEST: This proves signature verification happens
    BEFORE JSON parsing. If this test fails, the implementation is vulnerable.

    Expected: "Invalid signature" (signature checked first)
    NOT: "Invalid JSON" (would indicate JSON parsing before auth)
    """
    malformed_json = b"{this is not valid json at all!}"
    invalid_signature = "INVALID_SIGNATURE_67890"

    response = client.post(
        "/webhooks/razorpay",
        content=malformed_json,
        headers={
            "X-Razorpay-Signature": invalid_signature,
            "Content-Type": "application/json",
        },
    )

    # MUST return 401 (signature error), NOT 400 (JSON error)
    assert response.status_code == 401, \
        f"Expected 401 (signature error), got {response.status_code}. " \
        f"This indicates JSON parsing before signature verification!"

    data = response.json()
    assert "Invalid signature" in data["error"], \
        f"Expected 'Invalid signature', got: {data.get('error')}. " \
        f"JSON parsing happened before signature verification!"

    # Explicitly assert JSON error is NOT returned
    assert "JSON" not in data["error"], \
        "Received JSON parsing error without signature verification!"


def test_malformed_json_with_valid_signature_returns_invalid_json(client, webhook_secret):
    """
    TEST 4: Malformed JSON + valid signature → invalid JSON response.

    This proves that with a valid signature, JSON parsing errors are reported.
    """
    malformed_json = b"{not valid json}"
    signature = sign_payload(malformed_json, webhook_secret)

    response = client.post(
        "/webhooks/razorpay",
        content=malformed_json,
        headers={
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    # With valid signature, should get JSON parsing error
    assert response.status_code == 400
    data = response.json()
    assert "Invalid JSON" in data["error"] or "JSON" in data["error"]


def test_missing_signature_rejected_before_parsing(client):
    """
    TEST 5: Missing signature + valid-looking JSON → rejected before parsing.

    Ensures missing signature is caught before JSON processing.
    """
    payload = {
        "id": "evt_security_003",
        "event": "payment_link.paid",
        "payload": {"payment_link": {"entity": {"id": "plink_test"}}},
    }

    payload_bytes = json.dumps(payload).encode()

    response = client.post(
        "/webhooks/razorpay",
        content=payload_bytes,
        headers={
            # NO X-Razorpay-Signature header
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert "Missing signature" in data["error"] or "signature" in data["error"].lower()


def test_modified_body_with_original_signature_rejected(client, webhook_secret):
    """
    TEST 6: Modified body with original valid signature → rejected.

    Ensures tampering is detected.
    """
    original_payload = {
        "id": "evt_security_004",
        "event": "payment_link.paid",
        "payload": {"payment_link": {"entity": {"amount": 10000}}},
    }

    original_bytes = json.dumps(original_payload).encode()
    signature = sign_payload(original_bytes, webhook_secret)

    # Modify payload AFTER signing (attacker attempt)
    modified_payload = original_payload.copy()
    modified_payload["payload"]["payment_link"]["entity"]["amount"] = 100000  # 10x!
    modified_bytes = json.dumps(modified_payload).encode()

    response = client.post(
        "/webhooks/razorpay",
        content=modified_bytes,  # Modified body
        headers={
            "X-Razorpay-Signature": signature,  # Original signature
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid signature" in data["error"]


def test_one_character_modification_detected(client, webhook_secret):
    """
    TEST 7: One-character body modification → rejected.

    Ensures even tiny tampering is detected.
    """
    payload = {"id": "evt_security_005", "event": "payment_link.paid"}
    payload_bytes = json.dumps(payload).encode()
    signature = sign_payload(payload_bytes, webhook_secret)

    # Modify one character
    modified_bytes = payload_bytes.replace(b"005", b"006")

    response = client.post(
        "/webhooks/razorpay",
        content=modified_bytes,
        headers={
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert "Invalid signature" in data["error"]


def test_empty_signature_rejected(client):
    """
    TEST: Empty signature string → rejected before parsing.
    """
    payload = {"id": "evt_security_006", "event": "payment_link.paid"}
    payload_bytes = json.dumps(payload).encode()

    response = client.post(
        "/webhooks/razorpay",
        content=payload_bytes,
        headers={
            "X-Razorpay-Signature": "",  # Empty string
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    data = response.json()
    # Either "Missing signature" or "Invalid signature" is acceptable
    assert "signature" in data["error"].lower()


def test_signature_verification_uses_raw_body(client, webhook_secret):
    """
    TEST: Signature verification uses raw body bytes, not parsed/reserialized JSON.

    Different JSON serialization can produce different byte representations
    (whitespace, key order). Signature MUST be verified against the exact
    raw bytes received.
    """
    # Payload with extra whitespace
    payload_with_whitespace = b'{"id": "evt_007",  "event":  "payment_link.paid"  }'

    # Sign the exact bytes (with whitespace)
    signature = sign_payload(payload_with_whitespace, webhook_secret)

    response = client.post(
        "/webhooks/razorpay",
        content=payload_with_whitespace,
        headers={
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    # Should accept because signature matches exact raw bytes
    # May return 400 (execution not found) but signature was valid
    assert response.status_code in [200, 400]

    if response.status_code == 400:
        data = response.json()
        # Should NOT be "Invalid signature"
        assert "Invalid signature" not in data.get("error", "")


def test_security_regression_documentation():
    """
    REGRESSION TEST DOCUMENTATION

    This test exists to document the critical security requirement:

    "Signature verification MUST precede JSON parsing."

    If test_malformed_json_with_invalid_signature_returns_invalid_signature
    fails, it indicates that the implementation is parsing JSON before
    verifying signatures, which is a security vulnerability.

    An attacker could:
    1. Send malformed JSON without a valid signature
    2. Trigger expensive JSON parsing
    3. Probe for JSON validation errors
    4. Potentially exploit JSON parser vulnerabilities

    All without valid authentication.

    This test must ALWAYS pass.
    """
    # This is a documentation test - always passes
    # The actual security verification is in the tests above
    assert True, "Signature verification MUST precede JSON parsing"
