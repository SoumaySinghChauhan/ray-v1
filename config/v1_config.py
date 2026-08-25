"""
RAY V1 Configuration Layer

All configuration values are typed and validated.
Changes to defaults must be documented in decision log.
"""

from dataclasses import dataclass, field
from typing import Literal
import os
from decimal import Decimal


@dataclass(frozen=True)
class RecoveryConfig:
    """Recovery optimization configuration."""

    # RAY's assumption about organic recovery (without intervention)
    # This is NOT simulator ground truth
    assumed_organic_recovery_rate: float = 0.04

    # Daily operational limits
    max_actions_per_day: int = 10
    max_contacts_per_customer_per_day: int = 1

    # Customer protection
    do_not_contact_fraction: float = 0.05

    # Autonomous action limits (INR)
    autonomous_amount_limit: Decimal = Decimal("25000")

    # LLM thresholds
    llm_diagnosis_confidence_threshold: float = 0.70

    def __post_init__(self):
        """Validate configuration."""
        assert 0.0 <= self.assumed_organic_recovery_rate <= 1.0
        assert self.max_actions_per_day > 0
        assert self.max_contacts_per_customer_per_day > 0
        assert 0.0 <= self.do_not_contact_fraction <= 1.0
        assert self.autonomous_amount_limit > 0
        assert 0.0 <= self.llm_diagnosis_confidence_threshold <= 1.0


@dataclass(frozen=True)
class CostConfig:
    """Economic modeling costs (synthetic assumptions for V1)."""

    # Intervention costs (INR)
    payment_link_intervention_cost: Decimal = Decimal("0")
    email_intervention_cost: Decimal = Decimal("0.50")  # Reserved for V1.5

    # Customer friction modeling
    customer_friction_cost_per_contact: Decimal = Decimal("5")

    # Risk penalty (V1 uses policy engine for hard safety)
    risk_penalty: Decimal = Decimal("0")

    def __post_init__(self):
        """Validate costs."""
        assert self.payment_link_intervention_cost >= 0
        assert self.email_intervention_cost >= 0
        assert self.customer_friction_cost_per_contact >= 0
        assert self.risk_penalty >= 0


@dataclass(frozen=True)
class SimulatorConfig:
    """Synthetic world generation configuration."""

    # Customer world
    total_customers: int = 1500
    historical_transactions_min: int = 20
    historical_transactions_max: int = 30
    current_opportunities: int = 1000

    # Data splits (by customer)
    train_customers: int = 550
    validation_customers: int = 150
    test_customers: int = 300

    # Temporal simulation
    simulation_days: int = 10

    # Payment amount distribution
    payment_amount_distribution: Literal["lognormal"] = "lognormal"
    payment_amount_max: Decimal = Decimal("100000")

    def __post_init__(self):
        """Validate simulator configuration."""
        assert self.total_customers == self.current_opportunities + 500
        assert (self.train_customers + self.validation_customers +
                self.test_customers) == self.current_opportunities
        assert self.historical_transactions_min > 0
        assert self.historical_transactions_max >= self.historical_transactions_min
        assert self.simulation_days > 0
        assert self.payment_amount_max > 0


@dataclass(frozen=True)
class ReproducibilityConfig:
    """Random seeds for reproducibility."""

    world_seed: int = 42
    training_seed: int = 43
    evaluation_seed: int = 44
    bootstrap_seed: int = 45


@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation protocol configuration."""

    bootstrap_iterations: int = 1000
    confidence_level: float = 0.95

    def __post_init__(self):
        """Validate evaluation configuration."""
        assert self.bootstrap_iterations > 0
        assert 0.0 < self.confidence_level < 1.0


@dataclass(frozen=True)
class VersionConfig:
    """Version tracking for reproducibility."""

    simulation_version: str = "1.0.0"
    dataset_version: str = "1.0.0"
    diagnosis_prompt_version: str = "1.0.0"
    diagnosis_model_version: str = "claude-3-5-sonnet-20241022"
    model_version: str = "1.0.0"
    optimizer_version: str = "1.0.0"
    policy_version: str = "1.0.0"
    evaluation_protocol_version: str = "1.0.0"


@dataclass(frozen=True)
class DatabaseConfig:
    """Database configuration."""

    url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/ray_dev"
    ))
    pool_size: int = 10
    max_overflow: int = 20


@dataclass(frozen=True)
class RazorpayConfig:
    """Razorpay API configuration."""

    key_id: str = field(default_factory=lambda: os.getenv("RAZORPAY_KEY_ID", ""))
    key_secret: str = field(default_factory=lambda: os.getenv("RAZORPAY_KEY_SECRET", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("RAZORPAY_WEBHOOK_SECRET", ""))

    def __post_init__(self):
        """Validate Razorpay configuration."""
        # In development, keys may be empty
        # In production, all must be set
        pass


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration."""

    provider: Literal["anthropic", "openai"] = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "anthropic")
    )
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv(
        "LLM_MODEL",
        "claude-3-5-sonnet-20241022"
    ))

    def __post_init__(self):
        """Validate LLM configuration."""
        assert self.provider in ("anthropic", "openai")


@dataclass(frozen=True)
class RAYConfig:
    """Complete RAY V1 configuration."""

    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    simulator: SimulatorConfig = field(default_factory=SimulatorConfig)
    reproducibility: ReproducibilityConfig = field(default_factory=ReproducibilityConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    versions: VersionConfig = field(default_factory=VersionConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    razorpay: RazorpayConfig = field(default_factory=RazorpayConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


# Singleton configuration instance
_config: RAYConfig | None = None


def get_config() -> RAYConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = RAYConfig()
    return _config


def reset_config() -> None:
    """Reset configuration (for testing only)."""
    global _config
    _config = None
