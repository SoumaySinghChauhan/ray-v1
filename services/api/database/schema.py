"""
RAY V1 Database Schema

Core entities for the V1 decision pipeline.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime, JSON, Text,
    ForeignKey, Index, Enum as SQLEnum, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum


Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================

class FailureClassDB(str, enum.Enum):
    """Payment failure classification."""
    SOFT_DECLINE = "soft_decline"
    HARD_DECLINE = "hard_decline"
    AUTHENTICATION_FAILURE = "authentication_failure"
    GATEWAY_ERROR = "gateway_error"
    UNKNOWN = "unknown"


class PolicyDecisionDB(str, enum.Enum):
    """Policy authorization decision."""
    ALLOW = "allow"
    BLOCK = "block"


class ActionTypeDB(str, enum.Enum):
    """Action type."""
    CREATE_PAYMENT_LINK = "create_payment_link"
    DO_NOTHING = "do_nothing"


class ActorTypeDB(str, enum.Enum):
    """Decision actor."""
    LLM = "llm"
    ML = "ml"
    OPTIMIZER = "optimizer"
    POLICY_ENGINE = "policy_engine"
    EXECUTOR = "executor"
    SYSTEM = "system"


# ============================================================================
# Core Entities
# ============================================================================

class Merchant(Base):
    """Merchant entity."""
    __tablename__ = "merchants"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    razorpay_account_id = Column(String(64), unique=True, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)

    # Configuration overrides (JSON)
    config_overrides = Column(JSON, nullable=True)

    # Relationships
    customers = relationship("Customer", back_populates="merchant")
    policies = relationship("MerchantPolicy", back_populates="merchant")


class Customer(Base):
    """Customer entity."""
    __tablename__ = "customers"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False)
    external_customer_id = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Do-not-contact flag
    do_not_contact = Column(Boolean, nullable=False, default=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="customers")
    payments = relationship("Payment", back_populates="customer")
    opportunities = relationship("RecoveryOpportunity", back_populates="customer")

    __table_args__ = (
        Index("idx_customer_merchant", "merchant_id"),
        Index("idx_customer_external", "merchant_id", "external_customer_id"),
    )


class Payment(Base):
    """Payment transaction."""
    __tablename__ = "payments"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False)
    razorpay_payment_id = Column(String(64), unique=True, nullable=True)

    # Payment details
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    payment_method = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False)

    # Failure information
    failure_reason = Column(String(255), nullable=True)
    failure_code = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    failed_at = Column(DateTime, nullable=True)
    recovered_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="payments")
    opportunities = relationship("RecoveryOpportunity", back_populates="payment")

    __table_args__ = (
        Index("idx_payment_customer", "customer_id"),
        Index("idx_payment_merchant", "merchant_id"),
        Index("idx_payment_status", "status"),
        CheckConstraint("amount > 0", name="positive_amount"),
    )


class WebhookEvent(Base):
    """Incoming Razorpay webhook event."""
    __tablename__ = "webhook_events"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    razorpay_event_id = Column(String(64), unique=True, nullable=True)

    # Payload
    payload = Column(JSON, nullable=False)
    signature_verified = Column(Boolean, nullable=False, default=False)

    # Processing
    processed = Column(Boolean, nullable=False, default=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_webhook_event_type", "event_type"),
        Index("idx_webhook_processed", "processed"),
    )


class RecoveryOpportunity(Base):
    """A recovery opportunity (failed payment)."""
    __tablename__ = "recovery_opportunities"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False)
    payment_id = Column(String(64), ForeignKey("payments.id"), nullable=False)

    # Opportunity details
    recoverable_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Decision state
    decision_made = Column(Boolean, nullable=False, default=False)
    decision_at = Column(DateTime, nullable=True)
    selected_action = Column(SQLEnum(ActionTypeDB), nullable=True)

    # Outcome (filled after action)
    recovered = Column(Boolean, nullable=True)
    recovery_amount = Column(Numeric(12, 2), nullable=True)
    recovery_at = Column(DateTime, nullable=True)

    # Simulated day (for evaluation)
    simulated_day = Column(Integer, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="opportunities")
    payment = relationship("Payment", back_populates="opportunities")
    predictions = relationship("ActionPrediction", back_populates="opportunity")
    optimization_runs = relationship("OptimizationRun", back_populates="opportunity")
    executions = relationship("ExecutionAttempt", back_populates="opportunity")
    outcomes = relationship("RecoveryOutcome", back_populates="opportunity")

    __table_args__ = (
        Index("idx_opportunity_customer", "customer_id"),
        Index("idx_opportunity_payment", "payment_id"),
        Index("idx_opportunity_simulated_day", "simulated_day"),
        CheckConstraint("recoverable_amount > 0", name="positive_recoverable_amount"),
    )


class ActionPrediction(Base):
    """ML prediction for an action on an opportunity."""
    __tablename__ = "action_predictions"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), ForeignKey("recovery_opportunities.id"), nullable=False)
    action_type = Column(SQLEnum(ActionTypeDB), nullable=False)

    # Prediction
    recovery_probability = Column(Numeric(5, 4), nullable=False)
    model_version = Column(String(50), nullable=False)
    features_used = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("RecoveryOpportunity", back_populates="predictions")

    __table_args__ = (
        Index("idx_prediction_opportunity", "opportunity_id"),
        CheckConstraint("recovery_probability >= 0 AND recovery_probability <= 1",
                       name="valid_probability"),
    )


class OptimizationRun(Base):
    """Economic optimization decision."""
    __tablename__ = "optimization_runs"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), ForeignKey("recovery_opportunities.id"), nullable=False)

    # Decision
    selected_action = Column(SQLEnum(ActionTypeDB), nullable=False)
    expected_value = Column(Numeric(12, 2), nullable=False)
    incremental_value = Column(Numeric(12, 2), nullable=False)

    # Alternatives
    alternatives_considered = Column(JSON, nullable=False)
    optimizer_version = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("RecoveryOpportunity", back_populates="optimization_runs")

    __table_args__ = (
        Index("idx_optimization_opportunity", "opportunity_id"),
    )


class MerchantPolicy(Base):
    """Merchant-specific policy configuration."""
    __tablename__ = "merchant_policies"

    id = Column(String(64), primary_key=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id"), nullable=False)
    policy_version = Column(String(50), nullable=False)

    # Policy configuration (JSON)
    rules = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="policies")

    __table_args__ = (
        Index("idx_policy_merchant", "merchant_id", "is_active"),
    )


class ExecutionAttempt(Base):
    """Action execution attempt."""
    __tablename__ = "execution_attempts"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), ForeignKey("recovery_opportunities.id"), nullable=False)
    action_type = Column(SQLEnum(ActionTypeDB), nullable=False)

    # Execution result
    success = Column(Boolean, nullable=False)
    external_reference = Column(String(255), nullable=True)  # e.g., Razorpay payment link ID
    error_message = Column(Text, nullable=True)

    # Idempotency
    idempotency_key = Column(String(255), unique=True, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("RecoveryOpportunity", back_populates="executions")

    __table_args__ = (
        Index("idx_execution_opportunity", "opportunity_id"),
        Index("idx_execution_idempotency", "idempotency_key"),
    )


class RecoveryOutcome(Base):
    """Observed recovery outcome."""
    __tablename__ = "recovery_outcomes"

    id = Column(String(64), primary_key=True)
    opportunity_id = Column(String(64), ForeignKey("recovery_opportunities.id"), nullable=False)

    # Outcome
    recovered = Column(Boolean, nullable=False)
    recovery_amount = Column(Numeric(12, 2), nullable=True)
    recovery_at = Column(DateTime, nullable=True)

    # Attribution
    attributed_to_action = Column(SQLEnum(ActionTypeDB), nullable=True)
    observation_window_days = Column(Integer, nullable=False, default=7)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    opportunity = relationship("RecoveryOpportunity", back_populates="outcomes")

    __table_args__ = (
        Index("idx_outcome_opportunity", "opportunity_id"),
    )


class AuditEvent(Base):
    """Audit trail event."""
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    actor = Column(SQLEnum(ActorTypeDB), nullable=False)
    opportunity_id = Column(String(64), nullable=True)
    event_type = Column(String(100), nullable=False)

    # Decision details
    decision = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Versioning
    policy_version = Column(String(50), nullable=True)
    model_version = Column(String(50), nullable=True)
    optimizer_version = Column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_audit_opportunity", "opportunity_id"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_actor", "actor"),
    )


class EvaluationRun(Base):
    """Evaluation/benchmark run record."""
    __tablename__ = "evaluation_runs"

    id = Column(String(64), primary_key=True)
    run_type = Column(String(50), nullable=False)  # e.g., "baseline", "ray_v1"

    # Configuration
    simulation_version = Column(String(50), nullable=False)
    dataset_version = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=True)
    optimizer_version = Column(String(50), nullable=True)
    policy_version = Column(String(50), nullable=True)
    evaluation_protocol_version = Column(String(50), nullable=False)

    # Results
    opportunities_evaluated = Column(Integer, nullable=False)
    actions_taken = Column(Integer, nullable=False)
    incremental_recovery = Column(Numeric(12, 2), nullable=True)
    confidence_interval_lower = Column(Numeric(12, 2), nullable=True)
    confidence_interval_upper = Column(Numeric(12, 2), nullable=True)

    # Metadata
    results = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_evaluation_run_type", "run_type"),
        Index("idx_evaluation_created", "created_at"),
    )
