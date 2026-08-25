"""
LLM diagnosis schema and validation.

The LLM provides DIAGNOSTIC ENRICHMENT, not ground truth.
It does NOT overwrite the canonical observable failure_class.
"""

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class DiagnosticClass(str, Enum):
    """
    LLM diagnostic classification.

    This is enrichment, not replacement for canonical failure_class.
    """

    SOFT_DECLINE = "SOFT_DECLINE"
    HARD_DECLINE = "HARD_DECLINE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    GATEWAY_ERROR = "GATEWAY_ERROR"
    UNKNOWN = "UNKNOWN"


class ReasonCode(str, Enum):
    """Constrained reason code vocabulary."""

    # Failure characteristics
    ISSUER_DECLINE = "ISSUER_DECLINE"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    LIKELY_TRANSIENT = "LIKELY_TRANSIENT"
    PERSISTENT_FAILURE = "PERSISTENT_FAILURE"
    AUTHENTICATION_ISSUE = "AUTHENTICATION_ISSUE"
    GATEWAY_ISSUE = "GATEWAY_ISSUE"

    # Customer context signals
    STRONG_PAYMENT_HISTORY = "STRONG_PAYMENT_HISTORY"
    WEAK_PAYMENT_HISTORY = "WEAK_PAYMENT_HISTORY"
    RECENT_FAILURE_PATTERN = "RECENT_FAILURE_PATTERN"
    HIGH_RECOVERY_HISTORY = "HIGH_RECOVERY_HISTORY"
    LOW_RECOVERY_HISTORY = "LOW_RECOVERY_HISTORY"

    # Payment context
    HIGH_VALUE_PAYMENT = "HIGH_VALUE_PAYMENT"
    LOW_VALUE_PAYMENT = "LOW_VALUE_PAYMENT"
    PAYMENT_METHOD_SIGNAL = "PAYMENT_METHOD_SIGNAL"

    # Diagnostic confidence
    LOW_CONTEXT_CONFIDENCE = "LOW_CONTEXT_CONFIDENCE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class DiagnosticStatus(str, Enum):
    """Diagnostic processing status."""

    SUCCESS = "SUCCESS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    LLM_CALL_FAILED = "LLM_CALL_FAILED"
    SAFE_HALT = "SAFE_HALT"


class LLMDiagnosticOutput(BaseModel):
    """
    Structured LLM diagnostic output.

    This is the raw LLM response schema.
    """

    diagnostic_class: DiagnosticClass
    reason_codes: list[ReasonCode] = Field(default_factory=list, max_length=10)
    diagnostic_summary: str = Field(min_length=10, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator('reason_codes')
    @classmethod
    def validate_reason_codes_not_empty(cls, v):
        """Ensure at least one reason code."""
        if not v:
            raise ValueError("At least one reason code required")
        return v

    @field_validator('reason_codes')
    @classmethod
    def validate_reason_codes_unique(cls, v):
        """Ensure no duplicate reason codes."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate reason codes not allowed")
        return v


class DiagnosisRecord(BaseModel):
    """
    Complete diagnosis record with metadata.

    This is stored in the enrichment dataset.
    """

    opportunity_id: str
    customer_id: str

    # LLM diagnostic output
    diagnostic_class: DiagnosticClass
    reason_codes: list[ReasonCode]
    diagnostic_summary: str
    confidence: float

    # Processing status
    diagnostic_status: DiagnosticStatus

    # Version metadata
    diagnosis_version: str
    diagnosis_prompt_version: str
    diagnosis_model_version: str
    diagnosis_schema_version: str

    # Processing metadata
    generation_timestamp: str
    retry_count: int = 0
    llm_call_duration_ms: float | None = None


class DiagnosisManifest(BaseModel):
    """Diagnosis batch processing manifest."""

    diagnosis_version: str
    diagnosis_prompt_version: str
    diagnosis_model_version: str
    diagnosis_schema_version: str
    llm_provider: str

    generation_timestamp: str
    opportunities_total: int
    diagnoses_successful: int
    diagnoses_low_confidence: int
    diagnoses_failed: int

    total_llm_calls: int
    total_retries: int
    total_duration_seconds: float

    confidence_threshold: float
