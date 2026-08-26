"""
Extended database models for Razorpay integration.

Extends the existing schema with fields required for webhook processing
and persistent execution tracking.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime, JSON, Text,
    ForeignKey, Index, Enum as SQLEnum, CheckConstraint, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

from database.schema import Base


class ExecutionStateEnum(str, enum.Enum):
    """Execution state for Payment Link creation."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"


class WebhookProcessingStatusEnum(str, enum.Enum):
    """Webhook processing status."""
    RECEIVED = "RECEIVED"
    VERIFIED = "VERIFIED"
    DUPLICATE = "DUPLICATE"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    UNMATCHED = "UNMATCHED"


class OutcomeTypeEnum(str, enum.Enum):
    """Recovery outcome type."""
    RECOVERED = "RECOVERED"
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class ExecutionAttemptExtended(Base):
    """
    Extended execution attempt model.

    Stores Payment Link execution details with full lifecycle tracking.
    """
    __tablename__ = "execution_attempts_extended"

    # Primary key
    id = Column(String(64), primary_key=True)

    # Core identifiers
    merchant_id = Column(String(64), nullable=False)
    opportunity_id = Column(String(64), nullable=False)
    action_type = Column(String(50), nullable=False)
    policy_version = Column(String(50), nullable=False)

    # Idempotency
    idempotency_key = Column(String(255), nullable=False, unique=True)

    # Razorpay identifiers
    reference_id = Column(String(255), nullable=False, index=True)
    razorpay_payment_link_id = Column(String(64), nullable=True, index=True)
    short_url = Column(String(500), nullable=True)

    # Execution state
    state = Column(SQLEnum(ExecutionStateEnum), nullable=False)

    # Payment details
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expire_by = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_exec_ext_merchant", "merchant_id"),
        Index("idx_exec_ext_opportunity", "opportunity_id"),
        Index("idx_exec_ext_idempotency", "idempotency_key"),
        Index("idx_exec_ext_reference", "reference_id"),
        Index("idx_exec_ext_payment_link", "razorpay_payment_link_id"),
        Index("idx_exec_ext_state", "state"),
        CheckConstraint("amount > 0", name="exec_ext_positive_amount"),
    )


class WebhookEventExtended(Base):
    """
    Extended webhook event model.

    Stores Razorpay webhook events with full processing lifecycle.
    """
    __tablename__ = "webhook_events_extended"

    # Primary key
    id = Column(String(64), primary_key=True)

    # Provider info
    provider = Column(String(50), nullable=False, default="razorpay")
    event_id = Column(String(255), nullable=False, unique=True)
    event_type = Column(String(100), nullable=False)

    # Payload
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)

    # Verification
    signature_verified = Column(Boolean, nullable=False, default=False)

    # Processing
    processing_status = Column(
        SQLEnum(WebhookProcessingStatusEnum),
        nullable=False,
        default=WebhookProcessingStatusEnum.RECEIVED
    )

    # Resolution
    execution_id = Column(String(64), nullable=True, index=True)
    opportunity_id = Column(String(64), nullable=True, index=True)
    razorpay_payment_link_id = Column(String(64), nullable=True, index=True)
    reference_id = Column(String(255), nullable=True, index=True)

    # Timestamps
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_webhook_ext_event_id", "event_id"),
        Index("idx_webhook_ext_event_type", "event_type"),
        Index("idx_webhook_ext_status", "processing_status"),
        Index("idx_webhook_ext_execution", "execution_id"),
        Index("idx_webhook_ext_opportunity", "opportunity_id"),
        Index("idx_webhook_ext_payment_link", "razorpay_payment_link_id"),
        Index("idx_webhook_ext_received", "received_at"),
        UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),
    )


class RecoveryOutcomeExtended(Base):
    """
    Extended recovery outcome model.

    Stores recovery outcomes from webhook events with full attribution.
    """
    __tablename__ = "recovery_outcomes_extended"

    # Primary key
    id = Column(String(64), primary_key=True)

    # Core identifiers
    opportunity_id = Column(String(64), nullable=False, index=True)
    execution_id = Column(String(64), nullable=False, index=True)

    # Outcome
    outcome_type = Column(SQLEnum(OutcomeTypeEnum), nullable=False)
    amount_recovered = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="INR")

    # Razorpay identifiers
    razorpay_payment_id = Column(String(64), nullable=True, index=True)
    razorpay_payment_link_id = Column(String(64), nullable=False, index=True)

    # Event source
    source_event_id = Column(String(255), nullable=False)
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Metadata
    notes = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_outcome_ext_opportunity", "opportunity_id"),
        Index("idx_outcome_ext_execution", "execution_id"),
        Index("idx_outcome_ext_payment_link", "razorpay_payment_link_id"),
        Index("idx_outcome_ext_payment", "razorpay_payment_id"),
        Index("idx_outcome_ext_type", "outcome_type"),
        Index("idx_outcome_ext_observed", "observed_at"),
    )


class ContactCount(Base):
    """
    Customer contact count tracking.

    Tracks contacts per customer per day for policy enforcement.
    """
    __tablename__ = "contact_counts"

    # Composite primary key
    merchant_id = Column(String(64), nullable=False, primary_key=True)
    customer_id = Column(String(64), nullable=False, primary_key=True)
    simulated_day = Column(Integer, nullable=False, primary_key=True)

    # Count
    contact_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_contact_merchant_customer_day", "merchant_id", "customer_id", "simulated_day"),
        CheckConstraint("contact_count >= 0", name="contact_count_non_negative"),
    )
