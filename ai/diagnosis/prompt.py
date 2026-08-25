"""
LLM diagnosis prompt template.

CRITICAL: The prompt must NOT expose hidden simulator variables.
Only observable information is provided.
"""

from typing import Any


DIAGNOSIS_PROMPT_VERSION = "1.0.0"


DIAGNOSIS_SYSTEM_PROMPT = """You are a payment failure diagnostic assistant for a revenue recovery system.

Your role is to analyze payment failure information and provide structured diagnostic enrichment.

CRITICAL CONSTRAINTS:

1. You are providing DIAGNOSTIC ENRICHMENT, not making action decisions.
2. You must NOT recommend specific recovery actions (payment links, emails, etc.).
3. You must NOT calculate expected values or optimize decisions.
4. You must provide diagnostic classification and reasoning only.

INPUT:
- Observable payment failure information
- Customer payment history summary
- Failure description and context

OUTPUT:
- Diagnostic classification (SOFT_DECLINE, HARD_DECLINE, AUTHENTICATION_FAILURE, GATEWAY_ERROR, UNKNOWN)
- Reason codes (constrained vocabulary)
- Diagnostic summary (human-readable explanation)
- Confidence score (0.0 to 1.0)

DIAGNOSTIC CLASSES:

SOFT_DECLINE: Temporary, potentially recoverable failures
- Insufficient funds
- Temporary issuer decline
- Risk review in progress
- Daily/monthly limits exceeded

HARD_DECLINE: Persistent, structural failures
- Invalid/expired card
- Closed account
- Lost/stolen card
- Permanently blocked instrument

AUTHENTICATION_FAILURE: Authentication/verification issues
- 3D Secure failure
- OTP timeout
- Verification required
- Authentication challenge failed

GATEWAY_ERROR: Technical/system failures
- Network timeout
- Gateway unavailable
- Connection error
- Processing error

UNKNOWN: Insufficient information to classify

REASON CODES (select relevant ones):

Failure characteristics:
- ISSUER_DECLINE: Declined by issuing bank
- TEMPORARY_FAILURE: Likely temporary/transient
- LIKELY_TRANSIENT: Could resolve naturally
- PERSISTENT_FAILURE: Structural/permanent issue
- AUTHENTICATION_ISSUE: Auth/verification problem
- GATEWAY_ISSUE: Technical system issue

Customer context:
- STRONG_PAYMENT_HISTORY: Customer has good payment track record
- WEAK_PAYMENT_HISTORY: Customer has poor payment track record
- RECENT_FAILURE_PATTERN: Recent pattern of failures
- HIGH_RECOVERY_HISTORY: Customer often recovers from failures
- LOW_RECOVERY_HISTORY: Customer rarely recovers from failures

Payment context:
- HIGH_VALUE_PAYMENT: Significantly higher than customer average
- LOW_VALUE_PAYMENT: Significantly lower than customer average
- PAYMENT_METHOD_SIGNAL: Payment method relevant to diagnosis

Diagnostic quality:
- LOW_CONTEXT_CONFIDENCE: Limited context for confident diagnosis
- INSUFFICIENT_INFORMATION: Not enough information provided

RESPONSE FORMAT:

Return valid JSON only:

{
  "diagnostic_class": "SOFT_DECLINE",
  "reason_codes": ["TEMPORARY_FAILURE", "STRONG_PAYMENT_HISTORY"],
  "diagnostic_summary": "Brief human-readable diagnostic explanation (1-2 sentences)",
  "confidence": 0.85
}

CONFIDENCE SCORING:

0.9-1.0: Strong evidence, clear classification
0.7-0.9: Good evidence, reasonable confidence
0.5-0.7: Moderate evidence, some uncertainty
0.3-0.5: Weak evidence, significant uncertainty
0.0-0.3: Very weak evidence, low confidence

If information is insufficient or ambiguous, use lower confidence.
"""


def create_diagnosis_prompt(
    payment_amount: float,
    payment_method: str,
    currency: str,
    failure_class: str,
    failure_description: str,
    customer_history_summary: dict[str, Any],
) -> str:
    """
    Create diagnosis prompt for a specific opportunity.

    CRITICAL: Only observable information is provided.
    Hidden simulator variables must NEVER be included.

    Args:
        payment_amount: Payment amount in currency
        payment_method: Payment method (card, upi, netbanking, wallet)
        currency: Currency code
        failure_class: Canonical failure class (from simulator)
        failure_description: Human-readable failure description
        customer_history_summary: Observable customer history metrics

    Returns:
        Complete user prompt for LLM
    """

    # Format customer history in human-readable form
    hist = customer_history_summary

    history_text = f"""Customer Payment History:
- Total payments: {hist['historical_payment_count']}
- Successful payments: {hist['historical_success_count']}
- Failed payments: {hist['historical_failure_count']}
- Previously recovered failures: {hist['historical_recovery_count']}
- Historical recovery rate: {hist['historical_recovery_rate']:.1%}
- Customer lifetime value: {hist['customer_lifetime_value']:.2f} {currency}
- Average payment amount: {hist['avg_payment_amount']:.2f} {currency}
- Customer tenure: {hist['days_since_first_payment']} days"""

    # Contextualize payment amount
    if hist['avg_payment_amount'] > 0:
        ratio = payment_amount / float(hist['avg_payment_amount'])
        if ratio > 1.5:
            amount_context = f"This payment ({payment_amount:.2f} {currency}) is significantly HIGHER than customer's average ({hist['avg_payment_amount']:.2f} {currency})."
        elif ratio < 0.6:
            amount_context = f"This payment ({payment_amount:.2f} {currency}) is significantly LOWER than customer's average ({hist['avg_payment_amount']:.2f} {currency})."
        else:
            amount_context = f"This payment ({payment_amount:.2f} {currency}) is similar to customer's average ({hist['avg_payment_amount']:.2f} {currency})."
    else:
        amount_context = f"This payment: {payment_amount:.2f} {currency}."

    prompt = f"""Analyze this payment failure and provide diagnostic enrichment.

PAYMENT DETAILS:
- Amount: {payment_amount:.2f} {currency}
- Payment method: {payment_method}
- {amount_context}

FAILURE INFORMATION:
- Canonical classification: {failure_class}
- Failure description: "{failure_description}"

{history_text}

Provide diagnostic classification, reason codes, summary, and confidence score.

Return ONLY valid JSON matching the schema."""

    return prompt


def format_diagnosis_for_cache(
    opportunity_id: str,
    customer_id: str,
    llm_output: dict[str, Any],
    config,
    model_version: str,
    retry_count: int,
    duration_ms: float,
    status: str,
) -> dict[str, Any]:
    """
    Format diagnosis record for caching.

    Args:
        opportunity_id: Opportunity identifier
        customer_id: Customer identifier
        llm_output: Validated LLM output
        config: RAY configuration
        model_version: LLM model version
        retry_count: Number of retries
        duration_ms: Call duration in milliseconds
        status: Diagnostic status

    Returns:
        Complete diagnosis record
    """
    from datetime import datetime, timezone

    return {
        "opportunity_id": opportunity_id,
        "customer_id": customer_id,
        "diagnostic_class": llm_output["diagnostic_class"],
        "reason_codes": llm_output["reason_codes"],
        "diagnostic_summary": llm_output["diagnostic_summary"],
        "confidence": llm_output["confidence"],
        "diagnostic_status": status,
        "diagnosis_version": "1.0.0",
        "diagnosis_prompt_version": DIAGNOSIS_PROMPT_VERSION,
        "diagnosis_model_version": model_version,
        "diagnosis_schema_version": "1.0.0",
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_count": retry_count,
        "llm_call_duration_ms": duration_ms,
    }
