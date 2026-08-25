"""Test configuration layer."""

import pytest
import sys
from pathlib import Path
from decimal import Decimal

# Add config to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "config"))

from v1_config import (
    RecoveryConfig,
    CostConfig,
    SimulatorConfig,
    ReproducibilityConfig,
    get_config,
    reset_config,
)


def test_recovery_config_defaults():
    """Test default recovery configuration."""
    config = RecoveryConfig()

    assert config.assumed_organic_recovery_rate == 0.04
    assert config.max_actions_per_day == 10
    assert config.max_contacts_per_customer_per_day == 1
    assert config.do_not_contact_fraction == 0.05
    assert config.autonomous_amount_limit == Decimal("25000")
    assert config.llm_diagnosis_confidence_threshold == 0.70


def test_recovery_config_validation():
    """Test configuration validation."""
    # Invalid probability (> 1)
    with pytest.raises(AssertionError):
        RecoveryConfig(assumed_organic_recovery_rate=1.5)

    # Invalid probability (< 0)
    with pytest.raises(AssertionError):
        RecoveryConfig(assumed_organic_recovery_rate=-0.1)

    # Invalid max_actions_per_day
    with pytest.raises(AssertionError):
        RecoveryConfig(max_actions_per_day=0)


def test_cost_config_defaults():
    """Test default cost configuration."""
    config = CostConfig()

    assert config.payment_link_intervention_cost == Decimal("0")
    assert config.email_intervention_cost == Decimal("0.50")
    assert config.customer_friction_cost_per_contact == Decimal("5")
    assert config.risk_penalty == Decimal("0")


def test_simulator_config_data_split():
    """Test simulator data split configuration."""
    config = SimulatorConfig()

    # Verify split adds up correctly
    assert config.train_customers == 550
    assert config.validation_customers == 150
    assert config.test_customers == 300
    assert (config.train_customers + config.validation_customers +
            config.test_customers) == config.current_opportunities


def test_reproducibility_seeds():
    """Test reproducibility seeds are distinct."""
    config = ReproducibilityConfig()

    seeds = [
        config.world_seed,
        config.training_seed,
        config.evaluation_seed,
        config.bootstrap_seed,
    ]

    # All seeds should be distinct
    assert len(seeds) == len(set(seeds))


def test_global_config_singleton():
    """Test global configuration singleton."""
    reset_config()

    config1 = get_config()
    config2 = get_config()

    # Should return same instance
    assert config1 is config2
