"""
Core types and enums for RAY V1.
"""

from enum import Enum
from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class FailureClass(str, Enum):
    """V1 LLM-classified failure categories."""

    SOFT_DECLINE = "soft_decline"
    HARD_DECLINE = "hard_decline"
    AUTHENTICATION_FAILURE = "authentication_failure"
    GATEWAY_ERROR = "gateway_error"
    UNKNOWN = "unknown"


class PolicyDecision(str, Enum):
    """Policy engine authorization result."""

    ALLOW = "allow"
    BLOCK = "block"


class ActorType(str, Enum):
    """Decision actors for audit trail."""

    LLM = "llm"
    ML = "ml"
    OPTIMIZER = "optimizer"
    POLICY_ENGINE = "policy_engine"
    EXECUTOR = "executor"
    SYSTEM = "system"


# ============================================================================
# LLM Diagnosis Schema
# ============================================================================


class LLMDiagnosis(BaseModel):
    """Structured LLM diagnosis output."""

    model_config = ConfigDict(frozen=True)

    failure_class: FailureClass
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    explanation: str


# ============================================================================
# ML Prediction Schema
# ============================================================================


class ActionPrediction(BaseModel):
    """ML prediction for a specific action."""

    model_config = ConfigDict(frozen=True)

    action_type: str
    recovery_probability: float = Field(ge=0.0, le=1.0)
    model_version: str
    features_used: dict[str, Any]


# ============================================================================
# Optimizer Output Schema
# ============================================================================


class OptimizationResult(BaseModel):
    """Economic optimization result."""

    model_config = ConfigDict(frozen=True)

    selected_action: str
    expected_value: Decimal
    incremental_value: Decimal
    alternatives_considered: dict[str, Decimal]
    optimizer_version: str


# ============================================================================
# Policy Check Schema
# ============================================================================


class PolicyCheckResult(BaseModel):
    """Policy engine authorization result."""

    model_config = ConfigDict(frozen=True)

    decision: PolicyDecision
    reason: str
    policy_version: str
    checks_performed: list[str]


# ============================================================================
# Execution Result Schema
# ============================================================================


class ExecutionResult(BaseModel):
    """Action execution result."""

    model_config = ConfigDict(frozen=True)

    success: bool
    execution_id: str
    timestamp: datetime
    external_reference: str | None = None
    error_message: str | None = None


# ============================================================================
# Audit Event Schema
# ============================================================================


class AuditEvent(BaseModel):
    """Audit trail event."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    actor: ActorType
    opportunity_id: str
    event_type: str
    decision: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
