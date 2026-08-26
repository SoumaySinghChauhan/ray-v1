"""
Test that .env file is loaded correctly by FastAPI application.

Verifies configuration without revealing secrets.
"""

import sys
sys.path.insert(0, '.')

from services.api.main import app
from config.v1_config import get_config
from fastapi.testclient import TestClient


def test_dotenv_loading():
    """Test that .env file values are loaded into configuration."""
    print("\n" + "=" * 70)
    print("TEST: .env File Loading")
    print("=" * 70)

    # Test 1: Configuration object
    print("\n[Test 1] Direct Configuration Access")
    config = get_config()

    print(f"  RAZORPAY_MODE: {config.razorpay.mode}")
    print(f"  RAZORPAY_KEY_ID: {'✅ Present' if config.razorpay.key_id else '❌ Missing'}")
    print(f"  RAZORPAY_KEY_SECRET: {'✅ Present' if config.razorpay.key_secret else '❌ Missing'}")
    print(f"  RAZORPAY_WEBHOOK_SECRET: {'✅ Present' if config.razorpay.webhook_secret else '❌ Missing'}")

    config_ok = all([
        config.razorpay.mode == "test",
        config.razorpay.key_id,
        config.razorpay.key_secret,
        config.razorpay.webhook_secret,
    ])

    if config_ok:
        print("\n  ✅ Configuration loaded successfully")
    else:
        print("\n  ❌ Configuration incomplete")
        return False

    # Test 2: FastAPI endpoint
    print("\n[Test 2] FastAPI /config/verify Endpoint")
    client = TestClient(app)
    response = client.get("/config/verify")

    print(f"  Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"  Mode: {data['razorpay']['mode']}")
        print(f"  Key ID Present: {'✅' if data['razorpay']['key_id_present'] else '❌'}")
        print(f"  Key Secret Present: {'✅' if data['razorpay']['key_secret_present'] else '❌'}")
        print(f"  Webhook Secret Present: {'✅' if data['razorpay']['webhook_secret_present'] else '❌'}")

        endpoint_ok = all([
            data['razorpay']['mode'] == 'test',
            data['razorpay']['key_id_present'],
            data['razorpay']['key_secret_present'],
            data['razorpay']['webhook_secret_present'],
            data['dotenv_loaded'],
        ])

        if endpoint_ok:
            print("\n  ✅ FastAPI endpoint verified")
        else:
            print("\n  ❌ FastAPI endpoint incomplete")
            return False
    else:
        print(f"\n  ❌ Endpoint failed: {response.status_code}")
        return False

    # Test 3: Webhook secret available to route
    print("\n[Test 3] Webhook Secret Accessibility")

    # The webhook route uses os.getenv(), but since load_dotenv() is called
    # at module import, it should be available
    import os
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    if webhook_secret:
        print(f"  Length: {len(webhook_secret)} characters")
        print(f"  Format: {'✅ Valid (64 chars)' if len(webhook_secret) == 64 else '❌ Invalid'}")
        print("\n  ✅ Webhook secret accessible to routes")
    else:
        print("\n  ❌ Webhook secret not in environment")
        return False

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✅ .env file loaded successfully")
    print("✅ Configuration object populated")
    print("✅ FastAPI endpoints have access to secrets")
    print("✅ Webhook route will have access to RAZORPAY_WEBHOOK_SECRET")
    print()
    print("Application is ready to receive webhooks.")
    print()

    return True


if __name__ == "__main__":
    success = test_dotenv_loading()
    sys.exit(0 if success else 1)
