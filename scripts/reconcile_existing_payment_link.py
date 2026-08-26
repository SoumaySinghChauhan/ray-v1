#!/usr/bin/env python
"""
RAY V1 - One-Time Reconciliation Script

RECONCILES EXISTING PAYMENT LINK: plink_TUNHHQAh3D6rnQ

This script creates the missing execution record for a Payment Link that was
created before the persistence fix. It reconstructs the execution record from
the Razorpay webhook payload stored in the database.

SAFETY:
- ONE-TIME USE ONLY
- Requires --confirm-reconcile flag
- Only reconciles if execution does NOT already exist
- Uses actual data from webhook payload (not fabricated)

Usage:
    python scripts/reconcile_existing_payment_link.py --confirm-reconcile
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services" / "api"))

from database.session import SessionLocal
from database.models import ExecutionAttemptExtended, ExecutionStateEnum, WebhookEventExtended


def main():
    """Reconcile existing Payment Link with missing execution record."""
    parser = argparse.ArgumentParser(
        description="ONE-TIME reconciliation for existing Payment Link"
    )
    parser.add_argument(
        "--confirm-reconcile",
        action="store_true",
        help="Required: Confirm one-time reconciliation",
    )
    args = parser.parse_args()

    if not args.confirm_reconcile:
        print("ERROR: Must specify --confirm-reconcile")
        print("\nThis is a ONE-TIME reconciliation script for:")
        print("  Payment Link: plink_TUNHHQAh3D6rnQ")
        print("  Execution ID: 7f4413e3-698e-4a94-b92e-ebbe1e8f3a09")
        print("\nUsage:")
        print("  python scripts/reconcile_existing_payment_link.py --confirm-reconcile")
        sys.exit(1)

    print("=" * 70)
    print("RAY V1 - Payment Link Reconciliation")
    print("=" * 70)
    print()

    db = SessionLocal()

    try:
        # Step 1: Find webhook event with actual data
        print("[1/4] Loading webhook event data...")
        webhook_event = (
            db.query(WebhookEventExtended)
            .filter(WebhookEventExtended.event_id == "payment_link.paid")
            .first()
        )

        if not webhook_event:
            print("  ✗ Webhook event not found")
            print("     Expected event_id: payment_link.paid")
            sys.exit(1)

        payload = webhook_event.payload
        payment_link = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
        order = payload.get("payload", {}).get("order", {}).get("entity", {})
        notes = order.get("notes", {})

        payment_link_id = payment_link.get("id")
        reference_id = payment_link.get("reference_id")
        execution_id = notes.get("ray_execution_id")
        opportunity_id = notes.get("ray_opportunity_id")
        short_url = payment_link.get("short_url")
        amount = payment_link.get("amount", 0) / 100  # Convert paise to rupees

        print(f"  ✓ Webhook event found")
        print(f"  ✓ Payment Link ID: {payment_link_id}")
        print(f"  ✓ Execution ID: {execution_id}")
        print(f"  ✓ Opportunity ID: {opportunity_id}")
        print(f"  ✓ Reference ID: {reference_id}")
        print()

        # Step 2: Check if execution already exists
        print("[2/4] Checking for existing execution...")
        existing = (
            db.query(ExecutionAttemptExtended)
            .filter(ExecutionAttemptExtended.id == execution_id)
            .first()
        )

        if existing:
            print(f"  ✓ Execution already exists!")
            print(f"     ID: {existing.id}")
            print(f"     State: {existing.state}")
            print()
            print("SKIP: Execution record already exists. No reconciliation needed.")
            return

        print("  ✓ No existing execution (reconciliation needed)")
        print()

        # Step 3: Create execution record
        print("[3/4] Creating execution record...")

        # Generate idempotency key from execution_id (stable)
        idempotency_key = f"exec_{execution_id}"

        execution = ExecutionAttemptExtended(
            id=execution_id,
            merchant_id="test_merchant",
            opportunity_id=opportunity_id,
            action_type="create_payment_link",
            policy_version="1.0.0",
            idempotency_key=idempotency_key,
            reference_id=reference_id,
            razorpay_payment_link_id=payment_link_id,
            short_url=short_url,
            state=ExecutionStateEnum.COMPLETED,  # Payment Link was created successfully
            amount=amount,
            currency="INR",
            created_at=datetime.fromtimestamp(payload.get("created_at", 0), tz=timezone.utc),
            submitted_at=datetime.fromtimestamp(payload.get("created_at", 0), tz=timezone.utc),
            completed_at=datetime.fromtimestamp(payload.get("created_at", 0), tz=timezone.utc),
        )

        db.add(execution)
        db.commit()

        print("  ✓ Execution record created")
        print(f"     ID: {execution.id}")
        print(f"     Opportunity: {execution.opportunity_id}")
        print(f"     Payment Link: {execution.razorpay_payment_link_id}")
        print(f"     Reference: {execution.reference_id}")
        print(f"     State: {execution.state}")
        print()

        # Step 4: Verify
        print("[4/4] Verifying reconciliation...")
        verified = (
            db.query(ExecutionAttemptExtended)
            .filter(
                ExecutionAttemptExtended.razorpay_payment_link_id == payment_link_id
            )
            .first()
        )

        if verified:
            print("  ✓ Execution record verified in database")
            print()
            print("SUCCESS: Reconciliation complete!")
            print()
            print("Next steps:")
            print("  1. Existing webhook events will remain FAILED (historical)")
            print("  2. Future webhooks will resolve this execution")
            print("  3. Replaying the webhook will now find the execution")
            print()
        else:
            print("  ✗ Verification failed")
            sys.exit(1)

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

    print("=" * 70)
    print("Reconciliation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
