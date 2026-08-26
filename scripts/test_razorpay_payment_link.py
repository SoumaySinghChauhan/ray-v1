#!/usr/bin/env python
"""
RAY V1 - Razorpay Payment Link Test Script

SAFETY:
- TEST MODE ONLY
- Requires --confirm-test-link flag
- Creates exactly 1 Payment Link
- Validates all security constraints

Usage:
    python scripts/test_razorpay_payment_link.py --confirm-test-link
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.providers import create_razorpay_executor_from_env
from execution.service import ExecutionService
from policy.types import PolicyDecision, PolicyDecisionType
from datetime import datetime, timezone


def main():
    """Run single Payment Link test."""
    parser = argparse.ArgumentParser(
        description="Test Razorpay Payment Link creation (TEST MODE ONLY)"
    )
    parser.add_argument(
        "--confirm-test-link",
        action="store_true",
        help="Required: Confirm you want to create a real test Payment Link",
    )
    args = parser.parse_args()

    # Safety check: require explicit confirmation
    if not args.confirm_test_link:
        print("ERROR: Must specify --confirm-test-link to create a Payment Link")
        print("\nThis command creates a REAL Payment Link in Razorpay Test Mode.")
        print("Test Mode has a limit of 30 Payment Links per business.")
        print("\nUsage:")
        print("  python scripts/test_razorpay_payment_link.py --confirm-test-link")
        sys.exit(1)

    print("=" * 60)
    print("RAY V1 - Razorpay Payment Link Test")
    print("=" * 60)
    print()

    # Step 1: Verify environment
    print("[1/5] Verifying environment configuration...")

    mode = os.getenv("RAZORPAY_MODE", "")
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")

    if mode != "test":
        print(f"ERROR: RAZORPAY_MODE must be 'test' (got: '{mode}')")
        print("Set RAZORPAY_MODE=test in .env")
        sys.exit(1)

    if not key_id:
        print("ERROR: RAZORPAY_KEY_ID not set")
        print("Set RAZORPAY_KEY_ID in .env")
        sys.exit(1)

    if not key_secret:
        print("ERROR: RAZORPAY_KEY_SECRET not set")
        print("Set RAZORPAY_KEY_SECRET in .env")
        sys.exit(1)

    print(f"  ✓ RAZORPAY_MODE: {mode}")
    print(f"  ✓ RAZORPAY_KEY_ID: {key_id[:8]}..." if key_id else "")
    print(f"  ✓ RAZORPAY_KEY_SECRET: {'*' * 8}")
    print()

    # Step 2: Create executor
    print("[2/5] Creating Razorpay executor...")
    try:
        executor = create_razorpay_executor_from_env()
        print("  ✓ Executor created successfully")
        print()
    except Exception as e:
        print(f"  ✗ Failed to create executor: {e}")
        sys.exit(1)

    # Step 3: Create execution service
    print("[3/5] Creating execution service...")
    service = ExecutionService(executor=executor)
    print("  ✓ Execution service created")
    print()

    # Step 4: Create test Payment Link
    print("[4/5] Creating test Payment Link...")

    # Create test opportunity with unique ID
    import time
    unique_id = f"test_opp_{int(time.time())}"

    test_opportunity = {
        "opportunity_id": unique_id,
        "merchant_id": "test_merchant",
        "customer_id": "test_customer",
        "amount": 100.0,  # ₹100 (minimal amount for testing)
        "currency": "INR",
        "customer_contact": "+919876543210",
        "customer_email": "test@example.com",
        "customer_name": "Test Customer",
    }

    # Create ALLOW policy decision
    test_decision = PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id=unique_id,
        action_type="create_payment_link",
        policy_version="1.0.0",
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )

    try:
        result = service.execute_allowed_action(
            policy_decision=test_decision,
            opportunity=test_opportunity,
            simulated_day=1,
        )

        if result.success:
            print("  ✓ Payment Link created successfully")
            print()

            # Step 5: Display results
            print("[5/5] Test Payment Link Details:")
            print("-" * 60)
            print(f"  Execution ID:      {result.execution_id}")
            print(f"  Payment Link ID:   {result.razorpay_payment_link_id}")
            print(f"  Reference ID:      {result.reference_id}")
            print(f"  Short URL:         {result.short_url}")
            print(f"  State:             {result.state}")
            print("-" * 60)
            print()

            print("SUCCESS: Test Payment Link created successfully!")
            print()
            print("Next steps:")
            print("  1. Open the Short URL in your browser")
            print("  2. Test the payment flow (use Razorpay test cards)")
            print("  3. Verify webhook delivery (if webhook endpoint configured)")
            print()
            print("Test cards: https://razorpay.com/docs/payments/payments/test-card-upi-details/")
            print()

        else:
            print(f"  ✗ Payment Link creation failed")
            print(f"     Error: {result.error_message}")
            print(f"     Code:  {result.error_code}")
            print(f"     State: {result.state}")
            sys.exit(1)

    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
