"""
Operational seed data for RAY V1.

Safe, synthetic operational records — explicitly NOT the frozen 300-case
TEST benchmark. Seeds a merchant, customers, a short payment history per
customer, and one open recovery opportunity per customer, so the real
decision pipeline (ML -> economics -> policy) has something real to
evaluate against.

Idempotent: safe to call multiple times. Skips if the merchant already
exists.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from database.schema import (
    Merchant,
    Customer,
    Payment,
    RecoveryOpportunity,
    MerchantPolicy,
)
from config.v1_config import get_config

OPERATIONAL_MERCHANT_ID = "merchant_ray_ops"

# (customer_name, amount, failure_class, payment_method, prior_payments)
# prior_payments: list of (days_ago, status, amount)
_SCENARIOS = [
    ("Meridian Textiles", 4200.0, "soft_decline", "upi", [
        (30, "captured", 3900), (22, "captured", 4100), (15, "captured", 4050),
        (9, "failed", 3800), (5, "captured", 4200),
    ]),
    ("Kavya Sharma", 1850.0, "soft_decline", "card", [
        (18, "captured", 1700), (11, "captured", 1900),
    ]),
    ("Northline Logistics", 31000.0, "soft_decline", "netbanking", [
        (40, "captured", 29500), (28, "captured", 30800), (20, "captured", 31200),
        (12, "captured", 30500), (6, "failed", 29000), (3, "captured", 31000),
    ]),
    ("Arjun Mehta", 920.0, "hard_decline", "card", [
        (5, "failed", 900),
    ]),
    ("Bluepeak Studios", 7600.0, "gateway_error", "upi", [
        (25, "captured", 7200), (14, "captured", 7500),
    ]),
    ("Riya Kapoor", 2400.0, "authentication_failure", "card", [
        (16, "captured", 2200), (8, "captured", 2350),
    ]),
    ("Sagar Traders", 12750.0, "soft_decline", "netbanking", [
        (35, "captured", 11900), (21, "captured", 12300), (10, "captured", 12600),
    ]),
    ("Vantage Analytics", 5400.0, "soft_decline", "wallet", [
        (19, "captured", 5100), (7, "failed", 5000),
    ]),
    ("Ishaan Verma", 3100.0, "gateway_error", "upi", [
        (13, "captured", 2900),
    ]),
    ("Crestwave Media", 9800.0, "soft_decline", "card", [
        (27, "captured", 9200), (17, "captured", 9600), (9, "captured", 9750),
    ]),
]


def _hash_id(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:24]


def seed_operational_data(db: Session) -> dict:
    """
    Seed safe synthetic operational data. Idempotent.

    Returns a summary dict; {"already_seeded": True} if skipped.
    """
    existing = db.query(Merchant).filter(Merchant.id == OPERATIONAL_MERCHANT_ID).first()
    if existing:
        count = (
            db.query(RecoveryOpportunity)
            .filter(RecoveryOpportunity.merchant_id == OPERATIONAL_MERCHANT_ID)
            .count()
        )
        return {"already_seeded": True, "opportunities": count}

    config = get_config()
    now = datetime.now(timezone.utc)

    merchant = Merchant(
        id=OPERATIONAL_MERCHANT_ID,
        name="RAY Operational Demo Merchant",
        razorpay_account_id=None,
        created_at=now,
        is_active=True,
    )
    db.add(merchant)

    policy = MerchantPolicy(
        id=_hash_id("policy", OPERATIONAL_MERCHANT_ID, config.versions.policy_version),
        merchant_id=OPERATIONAL_MERCHANT_ID,
        policy_version=config.versions.policy_version,
        rules={
            "max_actions_per_day": config.recovery.max_actions_per_day,
            "max_contacts_per_customer_per_day": config.recovery.max_contacts_per_customer_per_day,
            "autonomous_amount_limit": str(config.recovery.autonomous_amount_limit),
        },
        created_at=now,
        is_active=True,
    )
    db.add(policy)

    created_opportunities = []

    for name, amount, failure_class, method, history in _SCENARIOS:
        customer_id = _hash_id("cust", OPERATIONAL_MERCHANT_ID, name)
        customer = Customer(
            id=customer_id,
            merchant_id=OPERATIONAL_MERCHANT_ID,
            external_customer_id=name.lower().replace(" ", "_"),
            email=f"{name.lower().replace(' ', '.')}@example.com",
            phone=None,
            created_at=now - timedelta(days=history[0][0] + 10 if history else 30),
            do_not_contact=False,
        )
        db.add(customer)

        # Prior payment history (used to compute observable ML features)
        for days_ago, status, hist_amount in history:
            hist_payment = Payment(
                id=_hash_id("pay", customer_id, str(days_ago), status),
                merchant_id=OPERATIONAL_MERCHANT_ID,
                customer_id=customer_id,
                razorpay_payment_id=None,
                amount=Decimal(str(hist_amount)),
                currency="INR",
                payment_method=method,
                status=status,
                failure_reason="issuer_decline" if status == "failed" else None,
                failure_code="51" if status == "failed" else None,
                created_at=now - timedelta(days=days_ago),
                failed_at=(now - timedelta(days=days_ago)) if status == "failed" else None,
                recovered_at=None,
            )
            db.add(hist_payment)

        # The current failed payment — the recovery opportunity itself
        failed_payment_id = _hash_id("pay", customer_id, "current")
        failed_payment = Payment(
            id=failed_payment_id,
            merchant_id=OPERATIONAL_MERCHANT_ID,
            customer_id=customer_id,
            razorpay_payment_id=None,
            amount=Decimal(str(amount)),
            currency="INR",
            payment_method=method,
            status="failed",
            failure_reason=failure_class,
            failure_code="51" if failure_class == "soft_decline" else "05",
            created_at=now - timedelta(hours=2),
            failed_at=now - timedelta(hours=2),
            recovered_at=None,
        )
        db.add(failed_payment)

        opportunity_id = _hash_id("opp", customer_id, "current")
        opportunity = RecoveryOpportunity(
            id=opportunity_id,
            merchant_id=OPERATIONAL_MERCHANT_ID,
            customer_id=customer_id,
            payment_id=failed_payment_id,
            recoverable_amount=Decimal(str(amount)),
            currency="INR",
            created_at=now - timedelta(hours=2),
            decision_made=False,
            decision_at=None,
            selected_action=None,
            recovered=None,
            recovery_amount=None,
            recovery_at=None,
            simulated_day=1,
        )
        db.add(opportunity)
        created_opportunities.append(opportunity_id)

    db.commit()

    return {"already_seeded": False, "opportunities": len(created_opportunities)}
