"""Test simulator components."""

import pytest
import sys
from pathlib import Path
from decimal import Decimal

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "config"))

from config import get_config
from simulator.world_model.customer_behavior import CustomerBehaviorModel, CustomerLatentState
from simulator.scenarios.failure_scenarios import FailureScenarioGenerator, FAILURE_SCENARIOS
from simulator.ground_truth.probability_model import GroundTruthProbabilityModel


def test_customer_generation_count():
    """Test that correct number of customers are generated."""
    model = CustomerBehaviorModel(seed=42)
    customers = model.generate_customers(count=100)

    assert len(customers) == 100
    assert all(isinstance(c, CustomerLatentState) for c in customers)


def test_customer_trait_ranges():
    """Test that customer traits are in valid ranges."""
    model = CustomerBehaviorModel(seed=42)
    customers = model.generate_customers(count=100)

    for customer in customers:
        assert 0.0 <= customer.payment_reliability <= 1.0
        assert 0.0 <= customer.recovery_affinity <= 1.0
        assert 0.0 <= customer.contact_responsiveness <= 1.0
        assert customer.spending_tier in ["low", "medium", "high"]
        assert customer.customer_maturity in ["new", "regular", "established"]


def test_customer_ids_unique():
    """Test that customer IDs are unique."""
    model = CustomerBehaviorModel(seed=42)
    customers = model.generate_customers(count=100)

    customer_ids = [c.customer_id for c in customers]
    assert len(customer_ids) == len(set(customer_ids))


def test_transaction_amount_generation():
    """Test transaction amount generation."""
    model = CustomerBehaviorModel(seed=42)
    config = get_config()

    customer = CustomerLatentState(
        customer_id="test_001",
        payment_reliability=0.8,
        recovery_affinity=0.7,
        contact_responsiveness=0.6,
        spending_tier="medium",
        customer_maturity="regular",
    )

    amount = model.generate_transaction_amount(
        customer,
        config.simulator.payment_amount_max
    )

    assert isinstance(amount, Decimal)
    assert amount > 0
    assert amount <= config.simulator.payment_amount_max


def test_failure_scenario_registry():
    """Test that failure scenario registry is complete."""
    assert len(FAILURE_SCENARIOS) > 0

    # Check all failure classes are represented
    classes = {s.failure_class for s in FAILURE_SCENARIOS}
    assert "soft_decline" in classes
    assert "hard_decline" in classes
    assert "authentication_failure" in classes
    assert "gateway_error" in classes
    assert "unknown" in classes


def test_failure_scenario_selection():
    """Test failure scenario selection."""
    generator = FailureScenarioGenerator(seed=42)

    scenarios = [generator.select_scenario() for _ in range(100)]

    # Should have variety
    classes = {s.failure_class for s in scenarios}
    assert len(classes) > 1  # Not all the same class


def test_failure_description_generation():
    """Test failure description generation."""
    generator = FailureScenarioGenerator(seed=42)
    scenario = generator.select_scenario()

    description = generator.generate_description(
        scenario,
        customer_history_summary="completed several previous payments"
    )

    assert isinstance(description, str)
    assert len(description) > 0
    # Should NOT contain scenario_id
    assert scenario.scenario_id not in description


def test_ground_truth_probability_ranges():
    """Test that ground truth probabilities are in valid ranges."""
    config = get_config()
    model = GroundTruthProbabilityModel(seed=42, config=config)

    # Create mock customer
    customer = CustomerLatentState(
        customer_id="test_001",
        payment_reliability=0.7,
        recovery_affinity=0.6,
        contact_responsiveness=0.5,
        spending_tier="medium",
        customer_maturity="regular",
    )

    # Create mock scenario
    from simulator.scenarios.failure_scenarios import FailureScenarioDefinition

    scenario = FailureScenarioDefinition(
        scenario_id="test_soft",
        failure_class="soft_decline",
        description_template="Test scenario",
        organic_recovery_modifier=0.8,
        payment_link_recovery_modifier=1.2,
        typical_recovery_window_hours=48,
    )

    # Calculate ground truth
    ground_truth = model.calculate_ground_truth(
        opportunity_id="opp_test_001",
        customer=customer,
        scenario=scenario,
        amount=Decimal("1000.00"),
        hours_since_failure=2,
        historical_recovery_rate=0.5,
        historical_payment_count=25,
    )

    # Validate probability ranges
    assert 0.0 <= ground_truth.true_organic_recovery_probability <= 1.0
    assert 0.0 <= ground_truth.true_payment_link_recovery_probability <= 1.0


def test_ground_truth_simulate_outcome():
    """Test outcome simulation."""
    config = get_config()
    model = GroundTruthProbabilityModel(seed=42, config=config)

    # Create mock ground truth with 100% payment link probability
    from simulator.ground_truth.probability_model import GroundTruthOutcome

    ground_truth = GroundTruthOutcome(
        opportunity_id="opp_test_001",
        true_organic_recovery_probability=0.0,
        true_payment_link_recovery_probability=1.0,
        scenario_id="test",
        scenario_failure_class="soft_decline",
        customer_payment_reliability=0.8,
        customer_recovery_affinity=0.7,
        customer_contact_responsiveness=0.6,
    )

    # Should always return True for 100% probability
    outcomes = [model.simulate_outcome(ground_truth, "payment_link") for _ in range(10)]
    assert all(outcomes)

    # Should always return False for 0% probability
    outcomes = [model.simulate_outcome(ground_truth, "do_nothing") for _ in range(10)]
    assert not any(outcomes)


def test_reproducibility():
    """Test that same seed produces same results."""
    model1 = CustomerBehaviorModel(seed=42)
    model2 = CustomerBehaviorModel(seed=42)

    customers1 = model1.generate_customers(count=10)
    customers2 = model2.generate_customers(count=10)

    for c1, c2 in zip(customers1, customers2):
        assert c1.customer_id == c2.customer_id
        assert c1.payment_reliability == c2.payment_reliability
        assert c1.recovery_affinity == c2.recovery_affinity
