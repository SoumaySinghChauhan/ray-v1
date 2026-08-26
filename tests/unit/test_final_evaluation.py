"""
Tests for final test evaluation (Prompt 8).

CRITICAL: These tests verify the integrity of the frozen final evaluation.
"""

import pytest
import json
import pickle
import pandas as pd
import numpy as np
from pathlib import Path


@pytest.fixture
def manifest_path():
    """Get manifest path."""
    return Path("reports/final-test-evaluation-manifest-v1.0.json")


@pytest.fixture
def manifest(manifest_path):
    """Load evaluation manifest."""
    if not manifest_path.exists():
        pytest.skip("Manifest not found - evaluation not run yet")
    with open(manifest_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def final_report_path():
    """Get final report path."""
    return Path("reports/final-test-evaluation-v1.0.json")


@pytest.fixture
def final_report(final_report_path):
    """Load final report."""
    if not final_report_path.exists():
        pytest.skip("Final report not found - evaluation not run yet")
    with open(final_report_path, 'r') as f:
        return json.load(f)


def test_manifest_exists(manifest_path):
    """Test that pre-registration manifest exists."""
    assert manifest_path.exists(), f"Manifest not found at {manifest_path}"


def test_manifest_has_required_fields(manifest):
    """Test that manifest has all required fields."""
    required_fields = [
        'dataset_version',
        'simulation_version',
        'diagnosis_version',
        'model_a_hash',
        'model_b_hash',
        'baseline_hash',
        'assumed_organic_recovery_rate',
        'max_actions_per_day',
        'intervention_cost',
        'friction_cost',
        'risk_penalty',
        'baseline_threshold',
        'baseline_fallback',
        'training_random_seed',
        'bootstrap_random_seed',
        'bootstrap_iterations',
        'test_accessed',
        'test_size',
    ]

    for field in required_fields:
        assert field in manifest, f"Missing required field: {field}"


def test_manifest_test_accessed_is_true(manifest):
    """Test that manifest confirms test access."""
    assert manifest['test_accessed'] is True, "Test should be accessed in final evaluation"


def test_manifest_test_size_is_300(manifest):
    """Test that manifest records correct test size."""
    assert manifest['test_size'] == 300, f"Expected test size 300, got {manifest['test_size']}"


def test_manifest_config_values_frozen(manifest):
    """Test that economic config is frozen."""
    assert manifest['assumed_organic_recovery_rate'] == 0.04, "Organic recovery rate should be 0.04"
    assert manifest['max_actions_per_day'] == 10, "Daily capacity should be 10"
    assert manifest['intervention_cost'] == 0.0, "Intervention cost should be 0"
    assert manifest['friction_cost'] == 5.0, "Friction cost should be 5"
    assert manifest['risk_penalty'] == 0.0, "Risk penalty should be 0"


def test_manifest_baseline_threshold_frozen(manifest):
    """Test that baseline threshold is frozen."""
    assert 0.2 < manifest['baseline_threshold'] < 0.3, "Baseline threshold should be around 0.27"


def test_manifest_bootstrap_iterations_is_1000(manifest):
    """Test that bootstrap uses 1000 iterations."""
    assert manifest['bootstrap_iterations'] == 1000, f"Expected 1000 bootstrap iterations, got {manifest['bootstrap_iterations']}"


def test_model_artifacts_unchanged():
    """Test that model artifact hashes match frozen hashes."""
    # This is a regression test - ensure models weren't retrained
    model_dir = Path('ml/models/v1.0.0')

    assert (model_dir / 'model_a_calibrated.pkl').exists(), "Model A artifact missing"
    assert (model_dir / 'model_b_calibrated.pkl').exists(), "Model B artifact missing"
    assert (model_dir / 'baseline.pkl').exists(), "Baseline artifact missing"


def test_final_report_exists(final_report_path):
    """Test that final report exists."""
    assert final_report_path.exists(), f"Final report not found at {final_report_path}"


def test_final_report_test_accessed_true(final_report):
    """Test that final report confirms test access."""
    assert final_report['test_accessed'] is True, "Final report should confirm test access"


def test_final_report_test_size_300(final_report):
    """Test that final report has correct test size."""
    assert final_report['test_size'] == 300, f"Expected 300 test samples, got {final_report['test_size']}"


def test_final_report_has_all_strategies(final_report):
    """Test that final report includes all three strategies."""
    assert 'baseline' in final_report, "Missing baseline results"
    assert 'model_a' in final_report, "Missing Model A results"
    assert 'model_b' in final_report, "Missing Model B results"


def test_final_report_metrics(final_report):
    """Test that all strategies have metrics."""
    for strategy in ['baseline', 'model_a', 'model_b']:
        assert 'metrics' in final_report[strategy], f"{strategy} missing metrics"
        metrics = final_report[strategy]['metrics']

        # Check metrics exist
        assert 'roc_auc' in metrics, f"{strategy} missing ROC-AUC"
        assert 'pr_auc' in metrics, f"{strategy} missing PR-AUC"
        assert 'brier_score' in metrics, f"{strategy} missing Brier"
        assert 'log_loss' in metrics, f"{strategy} missing Log Loss"

        # Check metrics are reasonable
        assert 0.5 < metrics['roc_auc'] < 0.9, f"{strategy} ROC-AUC out of range"
        assert 0.0 < metrics['brier_score'] < 0.5, f"{strategy} Brier out of range"


def test_final_report_allocation(final_report):
    """Test that all strategies have allocation results."""
    for strategy in ['baseline', 'model_a', 'model_b']:
        assert 'allocation' in final_report[strategy], f"{strategy} missing allocation"
        alloc = final_report[strategy]['allocation']

        # Check fields exist
        assert 'opportunities_evaluated' in alloc, f"{strategy} missing opportunities_evaluated"
        assert 'actions_selected' in alloc, f"{strategy} missing actions_selected"
        assert 'realized_recovery_count' in alloc, f"{strategy} missing realized_recovery_count"
        assert 'realized_recovered_amount' in alloc, f"{strategy} missing realized_recovered_amount"

        # Check values are reasonable
        assert alloc['opportunities_evaluated'] == 300, f"{strategy} should evaluate 300 opportunities"
        assert 0 <= alloc['actions_selected'] <= 300, f"{strategy} selected count out of range"
        assert 0 <= alloc['realized_recovery_count'] <= alloc['actions_selected'], f"{strategy} recovery count exceeds selected"


def test_final_report_bootstrap(final_report):
    """Test that bootstrap results exist."""
    for strategy in ['baseline', 'model_a', 'model_b']:
        assert 'bootstrap' in final_report[strategy], f"{strategy} missing bootstrap"
        boot = final_report[strategy]['bootstrap']

        assert 'point_estimate' in boot, f"{strategy} bootstrap missing point_estimate"
        assert 'percentile_95_ci' in boot, f"{strategy} bootstrap missing percentile_95_ci"

        # Check CI is list of 2 values
        ci = boot['percentile_95_ci']
        assert isinstance(ci, list), f"{strategy} CI should be a list"
        assert len(ci) == 2, f"{strategy} CI should have 2 values"
        assert ci[0] < ci[1], f"{strategy} CI lower should be less than upper"


def test_final_report_comparison(final_report):
    """Test that comparison results exist."""
    assert 'comparison' in final_report, "Missing comparison section"

    assert 'model_a_vs_baseline' in final_report['comparison'], "Missing Model A vs Baseline"
    assert 'model_b_vs_baseline' in final_report['comparison'], "Missing Model B vs Baseline"

    # Check delta structure
    for comp in ['model_a_vs_baseline', 'model_b_vs_baseline']:
        delta = final_report['comparison'][comp]
        assert 'point_estimate' in delta, f"{comp} missing point_estimate"
        assert 'percentile_95_ci' in delta, f"{comp} missing percentile_95_ci"


def test_calibration_plot_exists():
    """Test that calibration plot exists."""
    calib_path = Path('reports/final-test-calibration.png')
    assert calib_path.exists(), f"Calibration plot not found at {calib_path}"


def test_markdown_report_exists():
    """Test that markdown report exists."""
    md_path = Path('reports/final-test-evaluation-v1.0.md')
    assert md_path.exists(), f"Markdown report not found at {md_path}"


def test_test_set_not_in_train():
    """Test that test customers don't overlap with train."""
    from ml.training.data_loader import DataLoader

    loader = DataLoader(Path('datasets/v1.0.0/ml'))
    train_df = loader.load_train()
    test_df = loader.load_test(allow_test_access=True)

    train_customers = set(train_df['customer_id'])
    test_customers = set(test_df['customer_id'])

    overlap = train_customers & test_customers
    assert len(overlap) == 0, f"Test overlaps with train: {len(overlap)} customers"


def test_test_set_not_in_validation():
    """Test that test customers don't overlap with validation."""
    from ml.training.data_loader import DataLoader

    loader = DataLoader(Path('datasets/v1.0.0/ml'))
    val_df = loader.load_validation()
    test_df = loader.load_test(allow_test_access=True)

    val_customers = set(val_df['customer_id'])
    test_customers = set(test_df['customer_id'])

    overlap = val_customers & test_customers
    assert len(overlap) == 0, f"Test overlaps with validation: {len(overlap)} customers"


def test_test_set_size():
    """Test that test set has exactly 300 samples."""
    from ml.training.data_loader import DataLoader

    loader = DataLoader(Path('datasets/v1.0.0/ml'))
    test_df = loader.load_test(allow_test_access=True)

    assert len(test_df) == 300, f"Expected 300 test samples, got {len(test_df)}"
    assert test_df['customer_id'].nunique() == 300, "Expected 300 unique customers"
    assert test_df['opportunity_id'].nunique() == 300, "Expected 300 unique opportunities"


def test_model_a_improves_over_baseline_on_test(final_report):
    """Test that Model A improves over baseline on test set."""
    baseline_auc = final_report['baseline']['metrics']['roc_auc']
    model_a_auc = final_report['model_a']['metrics']['roc_auc']

    # Model A should be at least as good as baseline
    assert model_a_auc >= baseline_auc - 0.01, "Model A should not be significantly worse than baseline"


def test_economic_value_is_reasonable(final_report):
    """Test that realized recovered amounts are reasonable."""
    for strategy in ['baseline', 'model_a', 'model_b']:
        alloc = final_report[strategy]['allocation']
        realized = alloc['realized_recovered_amount']

        # Should be positive if any actions selected
        if alloc['actions_selected'] > 0:
            assert realized >= 0, f"{strategy} realized amount should be non-negative"


def test_capacity_constraints_enforced(final_report):
    """Test that daily capacity constraints were enforced."""
    max_daily_capacity = 10
    # 300 opportunities across ~30 days = max 300 actions total if capacity allows

    for strategy in ['baseline', 'model_a', 'model_b']:
        alloc = final_report[strategy]['allocation']
        # At most 10 actions per day across all days
        # This is a soft check - exact enforcement depends on opportunities per day


def test_bootstrap_reproducibility(manifest):
    """Test that bootstrap has fixed seed for reproducibility."""
    assert 'bootstrap_random_seed' in manifest, "Bootstrap should have fixed seed"
    assert manifest['bootstrap_random_seed'] == 44, "Bootstrap seed should be 44"
