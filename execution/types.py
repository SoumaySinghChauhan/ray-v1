"""
Execution types for RAY V1.

Defines execution states, outcomes, and data structures for Payment Link execution.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionState(str, Enum):
    """Execution attempt states."""

    PENDING = "PENDING"  # Authorized but not yet sent
    SUBMITTED = "SUBMITTED"  # Request sent to Razorpay
    SUCCEEDED = "SUCCEEDED"  # Payment Link created successfully
    FAILED = "FAILED"  # Definite failure from Razorpay
    UNKNOWN = "UNKNOWN"  # Outcome cannot be safely determined
    CANCELLED = "CANCELLED"  # Intentionally stopped


class OutcomeType(str, Enum):
    """Recovery outcome types."""

    RECOVERED = "RECOVERED"  # Full payment received
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"  # Partial payment
    EXPIRED = "EXPIRED"  # Payment Link expired
    CANCELLED = "CANCELLED"  # Payment Link cancelled
    UNKNOWN = "UNKNOWN"  # Outcome unknown


class WebhookEventType(str, Enum):
    """Razorpay webhook event types."""

    PAYMENT_LINK_PAID = "payment_link.paid"
    PAYMENT_LINK_PARTIALLY_PAID = "payment_link.partially_paid"
    PAYMENT_LINK_CANCELLED = "payment_link.cancelled"
    PAYMENT_LINK_EXPIRED = "payment_link.expired"


class WebhookProcessingStatus(str, Enum):
    """Webhook processing status."""

    RECEIVED = "RECEIVED"
    VERIFIED = "VERIFIED"
    DUPLICATE = "DUPLICATE"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class OpportunityState(str, Enum):
    """Opportunity states after execution."""

    SCORABLE = "SCORABLE"
    PLANNING = "PLANNING"
    ACTION_SELECTED = "ACTION_SELECTED"
    POLICY_CHECK = "POLICY_CHECK"
    EXECUTING = "EXECUTING"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    AWAITING_OUTCOME = "AWAITING_OUTCOME"
    RECOVERED = "RECOVERED"
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"
    SAFE_HALT = "SAFE_HALT"


@dataclass
class ExecutionAttempt:
    """
    Record of a Payment Link execution attempt.

    Tracks the lifecycle of creating a Razorpay Payment Link.
    """

    execution_id: str
    merchant_id: str
    opportunity_id: str
    action_type: str
    policy_version: str

    # Execution state
    state: str  # ExecutionState

    # Razorpay identifiers
    razorpay_payment_link_id: str | None
    reference_id: str
    short_url: str | None

    # Payment details
    amount: float
    currency: str

    # Timestamps
    created_at: str
    submitted_at: str | None
    completed_at: str | None
    expire_by: str | None

    # Result
    error_message: str | None
    error_code: str | None


@dataclass
class RecoveryOutcome:
    """
    Recovery outcome record.

    Tracks actual payment outcomes from Razorpay webhooks.
    """

    outcome_id: str
    opportunity_id: str
    execution_id: str

    outcome_type: str  # OutcomeType

    amount_recovered: float
    currency: str

    # Razorpay identifiers
    razorpay_payment_id: str | None
    razorpay_payment_link_id: str

    # Event source
    source_event_id: str
    observed_at: str

    # Additional data
    notes: dict[str, Any] | None


@dataclass
class WebhookEvent:
    """
    Razorpay webhook event record.

    Tracks received webhook events for idempotency and audit.
    """

    webhook_id: str
    provider: str  # "razorpay"
    event_id: str  # Razorpay event ID
    event_type: str  # WebhookEventType

    payload: dict[str, Any]
    payload_hash: str

    received_at: str
    signature_verified: bool
    processing_status: str  # WebhookProcessingStatus

    # Resolution
    execution_id: str | None
    opportunity_id: str | None

    error_message: str | None


@dataclass
class ExecutionResult:
    """
    Result of an execution attempt.

    Returned by execution providers.
    """

    success: bool
    execution_id: str
    state: str  # ExecutionState

    # Razorpay identifiers if successful
    razorpay_payment_link_id: str | None
    reference_id: str
    short_url: str | None

    error_message: str | None
    error_code: str | None
