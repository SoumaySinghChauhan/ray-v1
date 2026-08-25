"""
Feature manifest for RAY V1 ML models.

Every feature must be documented with provenance and observability status.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FeatureDefinition:
    """Definition of a single feature."""

    name: str
    source: str
    observable_at_decision_time: bool
    allowed_for_model: bool
    feature_type: Literal["numeric", "categorical", "boolean"]
    description: str
    missing_strategy: str


# Observable features (allowed for Model A and Model B)
OBSERVABLE_FEATURES = [
    FeatureDefinition(
        name="amount",
        source="payment.amount",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Payment amount in INR",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="log_amount",
        source="derived:log(payment.amount)",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Log-transformed payment amount",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="amount_to_avg_ratio",
        source="derived:payment.amount / customer.avg_payment_amount",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Current payment relative to customer average",
        missing_strategy="clip_1.0_if_zero_history",
    ),
    FeatureDefinition(
        name="payment_method",
        source="payment.payment_method",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="categorical",
        description="Payment method (card, upi, netbanking, wallet)",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="failure_class",
        source="payment.failure_class",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="categorical",
        description="Canonical failure classification",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="historical_payment_count",
        source="customer_history.payment_count",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Total historical payments",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="historical_success_count",
        source="customer_history.success_count",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Historical successful payments",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="historical_failure_count",
        source="customer_history.failure_count",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Historical failed payments",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="historical_recovery_count",
        source="customer_history.recovery_count",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Historical recovered failures",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="historical_recovery_rate",
        source="customer_history.recovery_rate",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Customer historical recovery rate",
        missing_strategy="validation_mean_fallback",
    ),
    FeatureDefinition(
        name="customer_lifetime_value",
        source="customer_history.lifetime_value",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Total customer lifetime value",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="log_customer_lifetime_value",
        source="derived:log(customer_history.lifetime_value + 1)",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Log-transformed customer LTV",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="days_since_first_payment",
        source="customer_history.days_since_first_payment",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Customer tenure in days",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="hours_since_failure",
        source="payment.hours_since_failure",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="Time since payment failure",
        missing_strategy="not_applicable",
    ),
]


# LLM diagnostic features (allowed for Model B only, requires real diagnosis)
LLM_DIAGNOSTIC_FEATURES = [
    FeatureDefinition(
        name="diagnostic_class",
        source="llm_diagnosis.diagnostic_class",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="categorical",
        description="LLM diagnostic classification",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="diagnostic_confidence",
        source="llm_diagnosis.confidence",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="numeric",
        description="LLM diagnostic confidence score",
        missing_strategy="not_applicable",
    ),
    FeatureDefinition(
        name="reason_code_temporary_failure",
        source="derived:llm_diagnosis.reason_codes",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="boolean",
        description="LLM identified temporary failure",
        missing_strategy="false",
    ),
    FeatureDefinition(
        name="reason_code_persistent_failure",
        source="derived:llm_diagnosis.reason_codes",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="boolean",
        description="LLM identified persistent failure",
        missing_strategy="false",
    ),
    FeatureDefinition(
        name="reason_code_strong_payment_history",
        source="derived:llm_diagnosis.reason_codes",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="boolean",
        description="LLM identified strong payment history",
        missing_strategy="false",
    ),
    FeatureDefinition(
        name="reason_code_high_recovery_history",
        source="derived:llm_diagnosis.reason_codes",
        observable_at_decision_time=True,
        allowed_for_model=True,
        feature_type="boolean",
        description="LLM identified high recovery history",
        missing_strategy="false",
    ),
]


# Forbidden features (NEVER allowed)
FORBIDDEN_FEATURE_PATTERNS = [
    "true_organic_recovery_probability",
    "true_payment_link_recovery_probability",
    "scenario_id",
    "customer_payment_reliability",
    "customer_recovery_affinity",
    "customer_contact_responsiveness",
    "latent",
    "hidden",
    "ground_truth",
    "actual_outcome",
    "recovered_at",
    "recovery_amount",
    # Target variable itself
    "target",
    "label",
]


def validate_feature_columns(
    columns: list[str],
    allow_identifiers: bool = True,
    allow_target: bool = False
) -> None:
    """
    Validate that feature columns don't contain forbidden patterns.

    Args:
        columns: Column names to validate
        allow_identifiers: Allow opportunity_id, customer_id, split
        allow_target: Allow 'target' column (for training datasets)

    Raises:
        ValueError: If forbidden features detected
    """
    forbidden_found = []

    # Columns to skip validation
    skip_columns = set()
    if allow_identifiers:
        skip_columns.update(["opportunity_id", "customer_id", "split"])
    if allow_target:
        skip_columns.update(["target", "label"])

    for col in columns:
        if col in skip_columns:
            continue

        col_lower = col.lower()
        for pattern in FORBIDDEN_FEATURE_PATTERNS:
            if pattern.lower() in col_lower:
                forbidden_found.append((col, pattern))

    if forbidden_found:
        raise ValueError(
            f"Forbidden features detected (leakage risk): {forbidden_found}"
        )


def get_model_a_features() -> list[str]:
    """Get feature names for Model A (observable only)."""
    return [f.name for f in OBSERVABLE_FEATURES]


def get_model_b_features() -> list[str]:
    """Get feature names for Model B (observable + LLM)."""
    return [f.name for f in OBSERVABLE_FEATURES + LLM_DIAGNOSTIC_FEATURES]
