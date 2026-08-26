"""
Regression test for webhook module import issues.

This test ensures that the FastAPI application can be imported
and webhook routes can process events without ModuleNotFoundError.
"""

import pytest
import json
import hmac
import hashlib


def test_fastapi_app_import():
    """
    Test that FastAPI app can be imported successfully.

    Regression test for: ModuleNotFoundError: No module named 'database'
    """
    from services.api.main import app

    assert app is not None
    assert app.title == "RAY - Revenue Recovery Orchestrator"


def test_webhook_route_exists():
    """Test that webhook route is registered."""
    from services.api.main import app

    routes = [route.path for route in app.routes]
    assert "/webhooks/razorpay" in routes


def test_webhook_database_imports_work(monkeypatch):
    """
    Test that webhook route can access database imports.

    This is a regression test for the ModuleNotFoundError when
    running with: python -m uvicorn services.api.main:app
    """
    from fastapi.testclient import TestClient
    from services.api.main import app

    # Set webhook secret
    webhook_secret = "test_webhook_secret_12345"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", webhook_secret)

    client = TestClient(app)

    # Create a valid signed webhook payload
    payload = {
        "id": "evt_module_test_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_module_test_001",
                    "reference_id": "RAY-module-test-001",
                    "status": "paid",
                    "amount": 10000,
                    "amount_paid": 10000,
                    "currency": "INR",
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_module_test_001",
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

    # Send webhook
    response = client.post(
        "/webhooks/razorpay",
        content=payload_bytes,
        headers={
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    # Should NOT get ModuleNotFoundError (500)
    # May get 400 (execution not found) but that means imports worked
    assert response.status_code in [200, 400], \
        f"Expected 200 or 400, got {response.status_code}: {response.text}"

    # Specifically check it's not an import error
    if response.status_code == 500:
        response_data = response.json()
        error_detail = response_data.get("detail", "")
        assert "ModuleNotFoundError" not in error_detail, \
            f"Got ModuleNotFoundError: {error_detail}"
        assert "No module named 'database'" not in error_detail, \
            f"Database import failed: {error_detail}"


def test_persistent_services_can_be_imported():
    """
    Test that persistent services can import database models.

    Regression test for imports in execution/service_persistent.py
    and execution/webhooks_persistent.py
    """
    # These imports should not raise ModuleNotFoundError
    from execution.service_persistent import PersistentExecutionService
    from execution.webhooks_persistent import PersistentWebhookHandler

    assert PersistentExecutionService is not None
    assert PersistentWebhookHandler is not None


def test_database_session_import():
    """Test that database session can be imported."""
    # This import pattern is used in services/api/main.py
    from database.session import SessionLocal

    assert SessionLocal is not None


def test_database_models_import():
    """Test that database models can be imported."""
    # This import pattern is used in execution files
    from database.models import (
        ExecutionAttemptExtended,
        WebhookEventExtended,
        RecoveryOutcomeExtended,
    )

    assert ExecutionAttemptExtended is not None
    assert WebhookEventExtended is not None
    assert RecoveryOutcomeExtended is not None
