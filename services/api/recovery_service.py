"""
Recovery decision service for RAY V1.

Orchestrates the real pipeline for a single operational opportunity:
    observable features -> Model A (frozen) -> economic value
    -> optimizer action selection -> policy authorization

This module does not reimplement any of those stages — it calls the real
ml_service, the real optimizer economics (mirrored from optimizer/core.py's
frozen formula, config-driven, not re-derived), and the real
policy.engine.DeterministicPolicyEngine. Execution goes through the real
PersistentExecutionService. Nothing here is a second source of truth.
"""

import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from database.schema import (
    Customer,
    Payment,
    RecoveryOpportunity,
    ActionPrediction,
    OptimizationRun,
    AuditEvent,
    ActionTypeDB,
    ActorTypeDB,
)
from database.models import (
    ExecutionAttemptExtended,
    WebhookEventExtended,
    RecoveryOutcomeExtended,
    ExecutionStateEnum,
)
from config.v1_config import get_config
from ml_service import predict_recovery_probability, model_a_metadata

from policy.engine import DeterministicPolicyEngine
from policy.types import MerchantPolicy, ExecutionState as PolicyExecutionState
from optimizer.core import ActionType

from execution.service_persistent import PersistentExecutionService
from execution.providers import MockPaymentLinkExecutor


class OpportunityNotFoundError(Exception):
    pass


class NotAllowedError(Exception):
    """Raised when execution is attempted without a fresh policy ALLOW."""


# ============================================================================
# Read helpers
# ============================================================================


def _opportunity_row(db: Session, opportunity_id: str) -> RecoveryOpportunity:
    opp = db.query(RecoveryOpportunity).filter(RecoveryOpportunity.id == opportunity_id).first()
    if opp is None:
        raise OpportunityNotFoundError(opportunity_id)
    return opp


def list_opportunities(db: Session, merchant_id: str) -> list[dict[str, Any]]:
    """Operational opportunities for a merchant — never the frozen TEST rows."""
    opps = (
        db.query(RecoveryOpportunity)
        .filter(RecoveryOpportunity.merchant_id == merchant_id)
        .order_by(RecoveryOpportunity.created_at.desc())
        .all()
    )
    return [_serialize_opportunity(db, o) for o in opps]


def get_opportunity(db: Session, opportunity_id: str) -> dict[str, Any]:
    opp = _opportunity_row(db, opportunity_id)
    return _serialize_opportunity(db, opp)


def _last_decision(db: Session, opportunity_id: str) -> dict[str, Any] | None:
    """
    Read-only summary of the most recently persisted decision AuditEvent for
    this opportunity. Never recomputes anything — it only reads whatever
    evaluate_opportunity() already wrote to the audit log, so list views
    (e.g. the Overview page) can surface real policy-block information
    without re-running the decision pipeline per row.
    """
    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.opportunity_id == opportunity_id, AuditEvent.event_type == "decision_evaluated")
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    if event is None:
        return None
    metadata = event.event_metadata or {}

    prediction = (
        db.query(ActionPrediction)
        .filter(ActionPrediction.opportunity_id == opportunity_id)
        .order_by(ActionPrediction.created_at.desc())
        .first()
    )
    run = (
        db.query(OptimizationRun)
        .filter(OptimizationRun.opportunity_id == opportunity_id)
        .order_by(OptimizationRun.created_at.desc())
        .first()
    )

    return {
        "selected_action": event.decision,
        "policy_decision": event.reason if event.reason in ("ALLOW", "BLOCK") else None,
        "policy_reason": metadata.get("policy_primary_reason"),
        "evaluated_at": event.timestamp.isoformat() if event.timestamp else None,
        "recovery_probability": float(prediction.recovery_probability) if prediction else None,
        "incremental_ev": float(run.incremental_value) if run else None,
        "expected_value": float(run.expected_value) if run else None,
    }


def _recovered_flag(db: Session, opportunity_id: str) -> bool | None:
    """
    Read-only recovery status, computed from the real persisted outcome —
    not the RecoveryOpportunity.recovered column, which the persistent
    webhook handler never writes to. None means no outcome has been
    observed yet; True/False reflect the latest verified outcome.
    """
    status = get_opportunity_status(db, opportunity_id)
    outcome = status["outcome"]
    if outcome is None:
        return None
    return outcome["outcome_type"] == "RECOVERED"


def _serialize_opportunity(db: Session, opp: RecoveryOpportunity) -> dict[str, Any]:
    customer = db.query(Customer).filter(Customer.id == opp.customer_id).first()
    payment = db.query(Payment).filter(Payment.id == opp.payment_id).first()
    return {
        "opportunity_id": opp.id,
        "merchant_id": opp.merchant_id,
        "customer_id": opp.customer_id,
        "customer_name": (customer.external_customer_id or customer.id).replace("_", " ").title() if customer else opp.customer_id,
        "amount": float(opp.recoverable_amount),
        "currency": opp.currency,
        "failure_class": payment.failure_reason if payment else None,
        "payment_method": payment.payment_method if payment else None,
        "failed_at": payment.failed_at.isoformat() if payment and payment.failed_at else None,
        "created_at": opp.created_at.isoformat() if opp.created_at else None,
        "decision_made": opp.decision_made,
        "selected_action": opp.selected_action.value if opp.selected_action else None,
        "recovered": _recovered_flag(db, opp.id),
        "last_decision": _last_decision(db, opp.id),
    }


# ============================================================================
# Feature construction (from real DB history — not the frozen TEST parquet)
# ============================================================================


def _build_features(db: Session, opp: RecoveryOpportunity, payment: Payment) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    history = (
        db.query(Payment)
        .filter(Payment.customer_id == opp.customer_id, Payment.id != payment.id)
        .all()
    )

    historical_payment_count = len(history)
    historical_success_count = sum(1 for p in history if p.status == "captured")
    historical_failure_count = sum(1 for p in history if p.status == "failed")

    captured_amounts = [float(p.amount) for p in history if p.status == "captured"]
    avg_payment_amount = sum(captured_amounts) / len(captured_amounts) if captured_amounts else 0.0
    customer_lifetime_value = sum(captured_amounts)

    outcomes = (
        db.query(RecoveryOutcomeExtended)
        .join(RecoveryOpportunity, RecoveryOutcomeExtended.opportunity_id == RecoveryOpportunity.id)
        .filter(RecoveryOpportunity.customer_id == opp.customer_id)
        .all()
    )
    historical_recovery_count = sum(1 for o in outcomes if o.outcome_type.value == "RECOVERED")
    historical_recovery_rate = (
        historical_recovery_count / historical_failure_count if historical_failure_count > 0 else 0.0
    )

    if history:
        first_payment_at = min(p.created_at for p in history)
        days_since_first_payment = max((now - first_payment_at.replace(tzinfo=timezone.utc)).days, 0)
    else:
        days_since_first_payment = 0

    failed_at = payment.failed_at.replace(tzinfo=timezone.utc) if payment.failed_at else now
    hours_since_failure = max((now - failed_at).total_seconds() / 3600, 0.0)

    amount = float(opp.recoverable_amount)

    return {
        "amount": amount,
        "log_amount": math.log1p(amount),
        "amount_to_avg_ratio": (amount / avg_payment_amount) if avg_payment_amount > 0 else 1.0,
        "payment_method": payment.payment_method or "card",
        "failure_class": payment.failure_reason or "unknown",
        "historical_payment_count": historical_payment_count,
        "historical_success_count": historical_success_count,
        "historical_failure_count": historical_failure_count,
        "historical_recovery_count": historical_recovery_count,
        "historical_recovery_rate": historical_recovery_rate,
        "customer_lifetime_value": customer_lifetime_value,
        "log_customer_lifetime_value": math.log1p(customer_lifetime_value),
        "days_since_first_payment": float(days_since_first_payment),
        "hours_since_failure": hours_since_failure,
    }


# ============================================================================
# Economics (frozen formula from optimizer/core.py, config-driven)
# ============================================================================


def _economic_value(amount: float, probability: float) -> dict[str, float]:
    config = get_config()
    gross_ev = probability * amount
    net_ev = (
        gross_ev
        - float(config.costs.payment_link_intervention_cost)
        - float(config.costs.customer_friction_cost_per_contact)
        - float(config.costs.risk_penalty)
    )
    do_nothing_ev = float(config.recovery.assumed_organic_recovery_rate) * amount
    incremental_ev = net_ev - do_nothing_ev
    return {
        "gross_ev": gross_ev,
        "net_ev": net_ev,
        "do_nothing_ev": do_nothing_ev,
        "incremental_ev": incremental_ev,
    }


def _merchant_policy(db: Session, merchant_id: str) -> MerchantPolicy:
    config = get_config()
    do_not_contact = {
        c.id for c in db.query(Customer).filter(Customer.merchant_id == merchant_id, Customer.do_not_contact.is_(True)).all()
    }
    return MerchantPolicy(
        merchant_id=merchant_id,
        max_actions_per_day=config.recovery.max_actions_per_day,
        max_contacts_per_customer_per_day=config.recovery.max_contacts_per_customer_per_day,
        autonomous_amount_limit=float(config.recovery.autonomous_amount_limit),
        policy_version=config.versions.policy_version,
        do_not_contact_list=do_not_contact,
    )


def _execution_state(db: Session, merchant_id: str) -> PolicyExecutionState:
    executed = (
        db.query(ExecutionAttemptExtended)
        .filter(
            ExecutionAttemptExtended.merchant_id == merchant_id,
            ExecutionAttemptExtended.state == ExecutionStateEnum.SUCCEEDED,
        )
        .all()
    )
    executed_actions = {(e.merchant_id, e.opportunity_id, e.action_type) for e in executed}

    contacts: dict[tuple[str, str, int], int] = {}
    from database.models import ContactCount

    for c in db.query(ContactCount).filter(ContactCount.merchant_id == merchant_id).all():
        contacts[(c.merchant_id, c.customer_id, c.simulated_day)] = c.contact_count

    return PolicyExecutionState(
        executed_actions=executed_actions,
        customer_contact_counts=contacts,
        opportunity_states={},
    )


# ============================================================================
# Evaluate — the full decision pipeline for one opportunity
# ============================================================================


def evaluate_opportunity(db: Session, opportunity_id: str) -> dict[str, Any]:
    opp = _opportunity_row(db, opportunity_id)
    payment = db.query(Payment).filter(Payment.id == opp.payment_id).first()
    if payment is None:
        raise OpportunityNotFoundError(f"payment for {opportunity_id}")

    config = get_config()

    features = _build_features(db, opp, payment)
    probability = predict_recovery_probability(features)
    econ = _economic_value(features["amount"], probability)

    recommended_action = (
        ActionType.CREATE_PAYMENT_LINK.value if econ["incremental_ev"] > 0 else ActionType.DO_NOTHING.value
    )

    opportunity_dict = {
        "opportunity_id": opp.id,
        "merchant_id": opp.merchant_id,
        "customer_id": opp.customer_id,
        "amount": features["amount"],
        "currency": opp.currency,
    }

    policy_result = None
    if recommended_action == ActionType.CREATE_PAYMENT_LINK.value:
        engine = DeterministicPolicyEngine(policy_version=config.versions.policy_version)
        merchant_policy = _merchant_policy(db, opp.merchant_id)
        execution_state = _execution_state(db, opp.merchant_id)
        decision = engine.evaluate_action(
            opportunity=opportunity_dict,
            action="create_payment_link",
            merchant_policy=merchant_policy,
            execution_state=execution_state,
            simulated_day=opp.simulated_day or 1,
        )
        policy_result = {
            "decision": decision.decision,
            "primary_reason": decision.primary_reason,
            "policy_version": decision.policy_version,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "passed": r.passed,
                    "reason": r.reason,
                }
                for r in decision.all_rule_results
            ],
        }

    now = datetime.now(timezone.utc)
    prediction = ActionPrediction(
        id=str(uuid.uuid4()),
        opportunity_id=opp.id,
        action_type=ActionTypeDB.CREATE_PAYMENT_LINK,
        recovery_probability=Decimal(str(round(probability, 4))),
        model_version=config.versions.model_version,
        features_used=features,
        created_at=now,
    )
    db.add(prediction)

    optimization_run = OptimizationRun(
        id=str(uuid.uuid4()),
        opportunity_id=opp.id,
        selected_action=ActionTypeDB(recommended_action),
        expected_value=Decimal(str(round(econ["net_ev"], 2))),
        incremental_value=Decimal(str(round(econ["incremental_ev"], 2))),
        alternatives_considered={"do_nothing": econ["do_nothing_ev"]},
        optimizer_version=config.versions.optimizer_version,
        created_at=now,
    )
    db.add(optimization_run)

    db.add(AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=now,
        actor=ActorTypeDB.SYSTEM,
        opportunity_id=opp.id,
        event_type="decision_evaluated",
        decision=recommended_action,
        reason=(policy_result["decision"] if policy_result else "no_action_needed"),
        event_metadata={
            "probability": probability,
            "incremental_ev": econ["incremental_ev"],
            "policy_primary_reason": policy_result["primary_reason"] if policy_result else None,
        },
        policy_version=config.versions.policy_version,
        model_version=config.versions.model_version,
        optimizer_version=config.versions.optimizer_version,
    ))

    opp.decision_made = True
    opp.decision_at = now
    opp.selected_action = ActionTypeDB(recommended_action)
    db.commit()

    return {
        "opportunity_id": opp.id,
        "model": model_a_metadata(),
        "prediction": {
            "recovery_probability": probability,
            "model_version": config.versions.model_version,
        },
        "economics": econ,
        "optimizer": {
            "recommended_action": recommended_action,
            "optimizer_version": config.versions.optimizer_version,
        },
        "policy": policy_result,
    }


# ============================================================================
# Execute — real Payment Link creation via the real persistent service
# ============================================================================


def execute_opportunity(db: Session, opportunity_id: str, executor) -> dict[str, Any]:
    """
    Execute create_payment_link for an opportunity.

    Re-evaluates policy server-side (never trusts a stale client-held
    decision) and only proceeds if the fresh result is ALLOW.
    """
    opp = _opportunity_row(db, opportunity_id)
    payment = db.query(Payment).filter(Payment.id == opp.payment_id).first()
    customer = db.query(Customer).filter(Customer.id == opp.customer_id).first()
    if payment is None:
        raise OpportunityNotFoundError(f"payment for {opportunity_id}")

    config = get_config()
    features = _build_features(db, opp, payment)
    probability = predict_recovery_probability(features)
    econ = _economic_value(features["amount"], probability)

    if econ["incremental_ev"] <= 0:
        raise NotAllowedError("Incremental EV is not positive; optimizer would not select this action")

    engine = DeterministicPolicyEngine(policy_version=config.versions.policy_version)
    merchant_policy = _merchant_policy(db, opp.merchant_id)
    execution_state = _execution_state(db, opp.merchant_id)
    opportunity_dict = {
        "opportunity_id": opp.id,
        "merchant_id": opp.merchant_id,
        "customer_id": opp.customer_id,
        "amount": features["amount"],
        "currency": opp.currency,
    }
    decision = engine.evaluate_action(
        opportunity=opportunity_dict,
        action="create_payment_link",
        merchant_policy=merchant_policy,
        execution_state=execution_state,
        simulated_day=opp.simulated_day or 1,
    )

    if decision.decision != "ALLOW":
        raise NotAllowedError(decision.primary_reason or "Policy did not authorize this action")

    service = PersistentExecutionService(executor=executor, db_session=db)
    exec_opportunity = {
        "merchant_id": opp.merchant_id,
        "customer_id": opp.customer_id,
        "amount": features["amount"],
        "currency": opp.currency,
        "customer_email": customer.email if customer else None,
    }
    result = service.execute_allowed_action(
        policy_decision=decision,
        opportunity=exec_opportunity,
        simulated_day=opp.simulated_day or 1,
    )

    db.add(AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        actor=ActorTypeDB.EXECUTOR,
        opportunity_id=opp.id,
        event_type="execution_attempted",
        decision="SUCCEEDED" if result.success else "FAILED",
        reason=result.error_message,
        event_metadata={"execution_id": result.execution_id, "payment_link_id": result.razorpay_payment_link_id},
        policy_version=config.versions.policy_version,
    ))
    db.commit()

    return {
        "success": result.success,
        "execution_id": result.execution_id,
        "state": result.state,
        "payment_link_id": result.razorpay_payment_link_id,
        "reference_id": result.reference_id,
        "short_url": result.short_url,
        "error_message": result.error_message,
    }


# ============================================================================
# Status polling
# ============================================================================


def get_opportunity_status(db: Session, opportunity_id: str) -> dict[str, Any]:
    execution = (
        db.query(ExecutionAttemptExtended)
        .filter(ExecutionAttemptExtended.opportunity_id == opportunity_id)
        .order_by(ExecutionAttemptExtended.created_at.desc())
        .first()
    )
    if execution is None:
        return {"execution": None, "webhook": None, "outcome": None}

    webhook = (
        db.query(WebhookEventExtended)
        .filter(WebhookEventExtended.execution_id == execution.id)
        .order_by(WebhookEventExtended.received_at.desc())
        .first()
    )
    outcome = (
        db.query(RecoveryOutcomeExtended)
        .filter(RecoveryOutcomeExtended.execution_id == execution.id)
        .order_by(RecoveryOutcomeExtended.observed_at.desc())
        .first()
    )

    return {
        "execution": {
            "execution_id": execution.id,
            "state": execution.state.value,
            "payment_link_id": execution.razorpay_payment_link_id,
            "reference_id": execution.reference_id,
            "short_url": execution.short_url,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
        },
        "webhook": (
            {
                "event_type": webhook.event_type,
                "signature_verified": webhook.signature_verified,
                "processing_status": webhook.processing_status.value,
                "received_at": webhook.received_at.isoformat() if webhook.received_at else None,
            }
            if webhook
            else None
        ),
        "outcome": (
            {
                "outcome_type": outcome.outcome_type.value,
                "amount_recovered": float(outcome.amount_recovered),
                "razorpay_payment_id": outcome.razorpay_payment_id,
                "observed_at": outcome.observed_at.isoformat() if outcome.observed_at else None,
            }
            if outcome
            else None
        ),
    }


# ============================================================================
# Audit trail
# ============================================================================


def get_audit_trail(db: Session, opportunity_id: str) -> dict[str, Any]:
    opp = _opportunity_row(db, opportunity_id)

    predictions = (
        db.query(ActionPrediction)
        .filter(ActionPrediction.opportunity_id == opportunity_id)
        .order_by(ActionPrediction.created_at.desc())
        .all()
    )
    runs = (
        db.query(OptimizationRun)
        .filter(OptimizationRun.opportunity_id == opportunity_id)
        .order_by(OptimizationRun.created_at.desc())
        .all()
    )
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.opportunity_id == opportunity_id)
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
    status = get_opportunity_status(db, opportunity_id)

    return {
        "opportunity": _serialize_opportunity(db, opp),
        "predictions": [
            {
                "recovery_probability": float(p.recovery_probability),
                "model_version": p.model_version,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in predictions
        ],
        "optimization_runs": [
            {
                "selected_action": r.selected_action.value,
                "expected_value": float(r.expected_value),
                "incremental_value": float(r.incremental_value),
                "optimizer_version": r.optimizer_version,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ],
        "events": [
            {
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "actor": e.actor.value,
                "event_type": e.event_type,
                "decision": e.decision,
                "reason": e.reason,
                "policy_version": e.policy_version,
                "model_version": e.model_version,
                "optimizer_version": e.optimizer_version,
            }
            for e in events
        ],
        "execution": status["execution"],
        "webhook": status["webhook"],
        "outcome": status["outcome"],
    }


def list_executions(db: Session, merchant_id: str) -> list[dict[str, Any]]:
    """Execution ledger for a merchant — real persisted rows, most recent first."""
    executions = (
        db.query(ExecutionAttemptExtended)
        .filter(ExecutionAttemptExtended.merchant_id == merchant_id)
        .order_by(ExecutionAttemptExtended.created_at.desc())
        .all()
    )
    out = []
    for e in executions:
        opp = db.query(RecoveryOpportunity).filter(RecoveryOpportunity.id == e.opportunity_id).first()
        customer = db.query(Customer).filter(Customer.id == opp.customer_id).first() if opp else None
        status = get_opportunity_status(db, e.opportunity_id)
        out.append({
            "execution_id": e.id,
            "opportunity_id": e.opportunity_id,
            "customer_name": (customer.external_customer_id or customer.id).replace("_", " ").title() if customer else e.opportunity_id,
            "state": e.state.value,
            "payment_link_id": e.razorpay_payment_link_id,
            "reference_id": e.reference_id,
            "short_url": e.short_url,
            "amount": float(e.amount),
            "currency": e.currency,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "webhook": status["webhook"],
            "outcome": status["outcome"],
        })
    return out


def default_executor():
    """
    Real Razorpay executor if TEST-mode credentials are configured,
    otherwise the mock executor. Never constructs a live-mode executor.
    """
    from execution.providers import create_razorpay_executor_from_env
    import os

    if os.getenv("RAZORPAY_MODE", "test") == "test" and os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET"):
        return create_razorpay_executor_from_env()
    return MockPaymentLinkExecutor()
