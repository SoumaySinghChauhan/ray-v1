"""Test LLM diagnosis components."""

import pytest
import sys
from pathlib import Path
from pydantic import ValidationError

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai.diagnosis.schema import (
    DiagnosticClass,
    ReasonCode,
    DiagnosticStatus,
    LLMDiagnosticOutput,
    DiagnosisRecord,
)
from ai.diagnosis.prompt import (
    DIAGNOSIS_PROMPT_VERSION,
    create_diagnosis_prompt,
    format_diagnosis_for_cache,
)
from config import get_config


def test_diagnostic_class_enum():
    """Test diagnostic class enum values."""
    assert DiagnosticClass.SOFT_DECLINE.value == "SOFT_DECLINE"
    assert DiagnosticClass.HARD_DECLINE.value == "HARD_DECLINE"
    assert DiagnosticClass.AUTHENTICATION_FAILURE.value == "AUTHENTICATION_FAILURE"
    assert DiagnosticClass.GATEWAY_ERROR.value == "GATEWAY_ERROR"
    assert DiagnosticClass.UNKNOWN.value == "UNKNOWN"


def test_reason_code_vocabulary():
    """Test reason code vocabulary is constrained."""
    # All reason codes should be in the enum
    codes = [
        "ISSUER_DECLINE",
        "TEMPORARY_FAILURE",
        "LIKELY_TRANSIENT",
        "PERSISTENT_FAILURE",
        "AUTHENTICATION_ISSUE",
        "GATEWAY_ISSUE",
        "STRONG_PAYMENT_HISTORY",
        "WEAK_PAYMENT_HISTORY",
        "RECENT_FAILURE_PATTERN",
        "HIGH_RECOVERY_HISTORY",
        "LOW_RECOVERY_HISTORY",
        "HIGH_VALUE_PAYMENT",
        "LOW_VALUE_PAYMENT",
        "PAYMENT_METHOD_SIGNAL",
        "LOW_CONTEXT_CONFIDENCE",
        "INSUFFICIENT_INFORMATION",
    ]

    for code in codes:
        assert code in [r.value for r in ReasonCode]


def test_llm_diagnostic_output_valid():
    """Test valid LLM diagnostic output."""
    output = LLMDiagnosticOutput(
        diagnostic_class=DiagnosticClass.SOFT_DECLINE,
        reason_codes=[ReasonCode.TEMPORARY_FAILURE, ReasonCode.STRONG_PAYMENT_HISTORY],
        diagnostic_summary="This is a valid diagnostic summary with sufficient length.",
        confidence=0.85,
    )

    assert output.diagnostic_class == DiagnosticClass.SOFT_DECLINE
    assert len(output.reason_codes) == 2
    assert output.confidence == 0.85


def test_llm_diagnostic_output_confidence_range():
    """Test confidence must be in [0, 1]."""
    # Valid
    LLMDiagnosticOutput(
        diagnostic_class=DiagnosticClass.SOFT_DECLINE,
        reason_codes=[ReasonCode.TEMPORARY_FAILURE],
        diagnostic_summary="Valid confidence range test.",
        confidence=0.5,
    )

    # Invalid: > 1.0
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            diagnostic_class=DiagnosticClass.SOFT_DECLINE,
            reason_codes=[ReasonCode.TEMPORARY_FAILURE],
            diagnostic_summary="Invalid confidence.",
            confidence=1.5,
        )

    # Invalid: < 0.0
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            diagnostic_class=DiagnosticClass.SOFT_DECLINE,
            reason_codes=[ReasonCode.TEMPORARY_FAILURE],
            diagnostic_summary="Invalid confidence.",
            confidence=-0.1,
        )


def test_llm_diagnostic_output_requires_reason_codes():
    """Test that at least one reason code is required."""
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            diagnostic_class=DiagnosticClass.SOFT_DECLINE,
            reason_codes=[],  # Empty not allowed
            diagnostic_summary="Missing reason codes.",
            confidence=0.8,
        )


def test_llm_diagnostic_output_no_duplicate_reason_codes():
    """Test that duplicate reason codes are not allowed."""
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            diagnostic_class=DiagnosticClass.SOFT_DECLINE,
            reason_codes=[
                ReasonCode.TEMPORARY_FAILURE,
                ReasonCode.TEMPORARY_FAILURE,  # Duplicate
            ],
            diagnostic_summary="Duplicate reason codes.",
            confidence=0.8,
        )


def test_llm_diagnostic_output_summary_length():
    """Test diagnostic summary length constraints."""
    # Too short
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            diagnostic_class=DiagnosticClass.SOFT_DECLINE,
            reason_codes=[ReasonCode.TEMPORARY_FAILURE],
            diagnostic_summary="Short",  # < 10 chars
            confidence=0.8,
        )

    # Too long
    with pytest.raises(ValidationError):
        LLMDiagnosticOutput(
            diagnostic_class=DiagnosticClass.SOFT_DECLINE,
            reason_codes=[ReasonCode.TEMPORARY_FAILURE],
            diagnostic_summary="x" * 501,  # > 500 chars
            confidence=0.8,
        )


def test_create_diagnosis_prompt_observable_only():
    """Test that diagnosis prompt uses only observable information."""
    history = {
        "historical_payment_count": 25,
        "historical_success_count": 20,
        "historical_failure_count": 5,
        "historical_recovery_count": 3,
        "historical_recovery_rate": 0.6,
        "customer_lifetime_value": 15000.0,
        "avg_payment_amount": 1500.0,
        "days_since_first_payment": 180,
    }

    prompt = create_diagnosis_prompt(
        payment_amount=2000.0,
        payment_method="card",
        currency="INR",
        failure_class="soft_decline",
        failure_description="Insufficient funds. Customer has good history.",
        customer_history_summary=history,
    )

    # Prompt should contain observable information
    assert "2000" in prompt
    assert "card" in prompt
    assert "soft_decline" in prompt
    assert "Insufficient funds" in prompt

    # Prompt should NOT contain hidden variables
    assert "true_organic" not in prompt.lower()
    assert "true_payment_link" not in prompt.lower()
    assert "scenario_id" not in prompt.lower()
    assert "latent" not in prompt.lower()


def test_diagnosis_prompt_version():
    """Test diagnosis prompt version is tracked."""
    assert DIAGNOSIS_PROMPT_VERSION == "1.0.0"


def test_format_diagnosis_for_cache():
    """Test diagnosis formatting for cache."""
    config = get_config()

    llm_output = {
        "diagnostic_class": "SOFT_DECLINE",
        "reason_codes": ["TEMPORARY_FAILURE"],
        "diagnostic_summary": "Test summary.",
        "confidence": 0.85,
    }

    record = format_diagnosis_for_cache(
        opportunity_id="opp_test_001",
        customer_id="cust_test_001",
        llm_output=llm_output,
        config=config,
        model_version="claude-3-5-sonnet-20241022",
        retry_count=0,
        duration_ms=250.0,
        status="SUCCESS",
    )

    assert record["opportunity_id"] == "opp_test_001"
    assert record["customer_id"] == "cust_test_001"
    assert record["diagnostic_class"] == "SOFT_DECLINE"
    assert record["confidence"] == 0.85
    assert record["diagnostic_status"] == "SUCCESS"
    assert record["diagnosis_version"] == "1.0.0"
    assert record["diagnosis_prompt_version"] == DIAGNOSIS_PROMPT_VERSION
    assert record["diagnosis_model_version"] == "claude-3-5-sonnet-20241022"
    assert record["retry_count"] == 0
    assert record["llm_call_duration_ms"] == 250.0


def test_diagnosis_record_validation():
    """Test complete diagnosis record validation."""
    record = DiagnosisRecord(
        opportunity_id="opp_001",
        customer_id="cust_001",
        diagnostic_class=DiagnosticClass.SOFT_DECLINE,
        reason_codes=[ReasonCode.TEMPORARY_FAILURE],
        diagnostic_summary="Valid diagnosis record.",
        confidence=0.85,
        diagnostic_status=DiagnosticStatus.SUCCESS,
        diagnosis_version="1.0.0",
        diagnosis_prompt_version="1.0.0",
        diagnosis_model_version="claude-3-5-sonnet-20241022",
        diagnosis_schema_version="1.0.0",
        generation_timestamp="2026-08-25T10:00:00Z",
        retry_count=0,
        llm_call_duration_ms=250.0,
    )

    assert record.opportunity_id == "opp_001"
    assert record.confidence == 0.85
