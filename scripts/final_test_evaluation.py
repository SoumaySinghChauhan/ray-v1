#!/usr/bin/env python
"""
RAY V1 - Prompt 8: Final Test Evaluation

CRITICAL: This is the FIRST and ONLY evaluation of the frozen 300-case TEST set.

This script:
1. Creates pre-registration manifest
2. Loads frozen TEST set (300 opportunities)
3. Loads frozen models (Baseline, Model A, Model B)
4. Generates predictions and metrics
5. Runs economic allocation
6. Calculates realized outcomes
7. Computes bootstrap uncertainty
8. Produces final reports

DO NOT modify frozen artifacts after test evaluation begins.
DO NOT rerun with changed parameters.
"""

import sys
import json
import pickle
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from decimal import Decimal

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, brier_score_loss, log_loss
from sklearn.calibration import calibration_curve

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ml.training.data_loader import DataLoader
from ml.features.feature_manifest import get_model_a_features
from optimizer.core import ConstrainedRecoveryOptimizer
from optimizer.interfaces import RecoveryProbabilityProvider, ActionEligibilityProvider, ActionEligibility
from config.v1_config import get_config


class FrozenEvaluationManifest:
    """Pre-registration manifest for test evaluation."""

    def __init__(self):
        self.config = get_config()
        self.manifest = {}

    def compute_artifact_hash(self, path: Path) -> str:
        """Compute SHA256 hash of artifact file."""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def create(self) -> Dict[str, Any]:
        """Create frozen evaluation manifest."""
        print("Creating Pre-Registration Manifest...")

        # Dataset versions
        self.manifest['dataset_version'] = '1.0.0'
        self.manifest['simulation_version'] = '1.0.0'
        self.manifest['diagnosis_version'] = 'local_v1'

        # Model artifact hashes
        model_dir = Path('ml/models/v1.0.0')
        self.manifest['model_a_hash'] = self.compute_artifact_hash(model_dir / 'model_a_calibrated.pkl')
        self.manifest['model_b_hash'] = self.compute_artifact_hash(model_dir / 'model_b_calibrated.pkl')
        self.manifest['baseline_hash'] = self.compute_artifact_hash(model_dir / 'baseline.pkl')

        # Configuration
        self.manifest['assumed_organic_recovery_rate'] = float(self.config.recovery.assumed_organic_recovery_rate)
        self.manifest['max_actions_per_day'] = self.config.recovery.max_actions_per_day
        self.manifest['intervention_cost'] = float(self.config.costs.payment_link_intervention_cost)
        self.manifest['friction_cost'] = float(self.config.costs.customer_friction_cost_per_contact)
        self.manifest['risk_penalty'] = float(self.config.costs.risk_penalty)

        # Load training metadata
        with open(model_dir / 'training_metadata_7c.json', 'r') as f:
            metadata = json.load(f)

        # Load baseline for threshold/fallback
        with open(model_dir / 'baseline.pkl', 'rb') as f:
            baseline = pickle.load(f)

        self.manifest['baseline_threshold'] = baseline.threshold
        self.manifest['baseline_fallback'] = baseline.cold_start_fallback
        self.manifest['model_a_selected'] = metadata['model_a']['selected']
        self.manifest['model_b_selected'] = metadata['model_b']['selected']
        self.manifest['model_b_status'] = metadata['model_b']['status']

        # Random seeds
        self.manifest['training_random_seed'] = metadata['random_seed']
        self.manifest['bootstrap_random_seed'] = 44  # Fixed for reproducibility
        self.manifest['bootstrap_iterations'] = 1000

        # Evaluation metadata
        self.manifest['evaluation_timestamp'] = datetime.now().isoformat()
        self.manifest['test_accessed'] = True
        self.manifest['test_size'] = 300

        print(f"  ✓ Manifest created")
        print(f"  ✓ Model A hash: {self.manifest['model_a_hash'][:16]}...")
        print(f"  ✓ Model B hash: {self.manifest['model_b_hash'][:16]}...")
        print(f"  ✓ Baseline hash: {self.manifest['baseline_hash'][:16]}...")

        return self.manifest

    def save(self, output_path: Path):
        """Save manifest to file."""
        with open(output_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)
        print(f"  ✓ Manifest saved to: {output_path}")


class ModelProbabilityProvider(RecoveryProbabilityProvider):
    """Adapter for frozen sklearn models."""

    def __init__(self, model, features, opportunities_df):
        self.model = model
        self.features = features
        self.opp_dict = {row['opportunity_id']: row for _, row in opportunities_df.iterrows()}

    def predict_payment_link_probability(self, opportunity: dict) -> float:
        opp_id = opportunity['opportunity_id']
        row = self.opp_dict[opp_id]
        feature_values = [row[feat] for feat in self.features]
        X = pd.DataFrame([feature_values], columns=self.features)
        prob = self.model.predict_proba(X)[0, 1]
        return float(prob)


class BaselineProbabilityProvider(RecoveryProbabilityProvider):
    """Adapter for baseline model."""

    def __init__(self, baseline, opportunities_df):
        self.baseline = baseline
        self.opp_dict = {row['opportunity_id']: row for _, row in opportunities_df.iterrows()}

    def predict_payment_link_probability(self, opportunity: dict) -> float:
        opp_id = opportunity['opportunity_id']
        row = self.opp_dict[opp_id]
        X = pd.DataFrame([row])
        prob = self.baseline.predict_proba(X)[0]
        return float(prob)


class SimpleEligibilityProvider(ActionEligibilityProvider):
    """Simple eligibility rules."""

    def check_eligibility(self, opportunity: dict, action: str) -> ActionEligibility:
        if action == "do_nothing":
            return ActionEligibility.ELIGIBLE
        if opportunity.get('amount', 0) > 25000:
            return ActionEligibility.INELIGIBLE
        return ActionEligibility.ELIGIBLE


class FinalTestEvaluator:
    """Final test evaluation orchestrator."""

    def __init__(self):
        self.config = get_config()
        self.data_dir = Path('datasets/v1.0.0/ml')
        self.model_dir = Path('ml/models/v1.0.0')
        self.output_dir = Path('reports')
        self.output_dir.mkdir(exist_ok=True)

        self.results = {}
        self.manifest = None
        self.test_df = None

    def step_0_preregistration(self):
        """Step 0: Create and save frozen evaluation manifest."""
        print("\n" + "=" * 70)
        print("STEP 0: PRE-REGISTRATION MANIFEST")
        print("=" * 70)

        manifest_builder = FrozenEvaluationManifest()
        self.manifest = manifest_builder.create()

        manifest_path = self.output_dir / 'final-test-evaluation-manifest-v1.0.json'
        manifest_builder.save(manifest_path)

    def step_1_load_test(self):
        """Step 1: Load TEST set (300 opportunities)."""
        print("\n" + "=" * 70)
        print("STEP 1: LOAD TEST SET")
        print("=" * 70)

        loader = DataLoader(self.data_dir)

        # Explicit test access
        print("\n⚠️  ACCESSING TEST SET - FIRST INTENTIONAL ACCESS")
        self.test_df = loader.load_test(allow_test_access=True)

        # Verify
        print(f"\nTest Set Loaded:")
        print(f"  Rows: {len(self.test_df)}")
        print(f"  Unique customers: {self.test_df['customer_id'].nunique()}")
        print(f"  Unique opportunities: {self.test_df['opportunity_id'].nunique()}")

        assert len(self.test_df) == 300, f"Expected 300 test rows, got {len(self.test_df)}"
        assert self.test_df['customer_id'].nunique() == 300, "Expected 300 unique customers"
        assert self.test_df['opportunity_id'].nunique() == 300, "Expected 300 unique opportunities"

        # Verify no overlap with train/validation
        train_df = loader.load_train()
        val_df = loader.load_validation()

        train_customers = set(train_df['customer_id'])
        val_customers = set(val_df['customer_id'])
        test_customers = set(self.test_df['customer_id'])

        assert len(train_customers & test_customers) == 0, "Test overlaps with train!"
        assert len(val_customers & test_customers) == 0, "Test overlaps with validation!"

        print(f"  ✓ No customer overlap with train")
        print(f"  ✓ No customer overlap with validation")
        print(f"\n  TEST_ACCESS = TRUE")

    def step_2_load_frozen_artifacts(self):
        """Step 2: Load frozen model artifacts."""
        print("\n" + "=" * 70)
        print("STEP 2: LOAD FROZEN ARTIFACTS")
        print("=" * 70)

        # Model A
        with open(self.model_dir / 'model_a_calibrated.pkl', 'rb') as f:
            self.model_a = pickle.load(f)
        print(f"  ✓ Model A: {self.model_a['model_type']}, {len(self.model_a['features'])} features")

        # Model B
        with open(self.model_dir / 'model_b_calibrated.pkl', 'rb') as f:
            self.model_b = pickle.load(f)
        print(f"  ✓ Model B: {self.model_b['model_type']}, {len(self.model_b['features'])} features")

        # Baseline
        with open(self.model_dir / 'baseline.pkl', 'rb') as f:
            self.baseline = pickle.load(f)
        print(f"  ✓ Baseline: threshold={self.baseline.threshold}, fallback={self.baseline.cold_start_fallback}")

    def step_3_construct_test_features(self):
        """Step 3: Construct test features for all models."""
        print("\n" + "=" * 70)
        print("STEP 3: CONSTRUCT TEST FEATURES")
        print("=" * 70)

        # Model A features
        base_features = get_model_a_features()
        X_test_a = self.test_df[base_features].copy()
        categorical_features = ['payment_method', 'failure_class']
        X_test_a_encoded = pd.get_dummies(X_test_a, columns=categorical_features, drop_first=True)

        # Align with Model A
        for col in self.model_a['features']:
            if col not in X_test_a_encoded.columns:
                X_test_a_encoded[col] = 0
        self.X_test_a = X_test_a_encoded[self.model_a['features']]

        print(f"\n  Model A features: {len(self.X_test_a.columns)}")

        # Model B features (with diagnosis integration)
        dx_path = Path('datasets/v1.0.0/diagnoses_local_v1/diagnoses.parquet')
        dx_df = pd.read_parquet(dx_path)

        # Merge diagnosis with test
        test_with_dx = self.test_df.merge(
            dx_df[['opportunity_id', 'diagnostic_class', 'confidence', 'diagnostic_status']],
            on='opportunity_id',
            how='left'
        )

        print(f"  Test diagnoses merged: {len(test_with_dx)}")
        print(f"  Missing diagnoses: {test_with_dx['diagnostic_class'].isna().sum()}")

        # Handle missing
        test_with_dx['diagnosis_missing'] = test_with_dx['diagnostic_class'].isna().astype(int)
        test_with_dx['diagnostic_class'] = test_with_dx['diagnostic_class'].fillna('UNKNOWN')
        test_with_dx['confidence'] = test_with_dx['confidence'].fillna(0.0)

        # Prepare Model B features
        X_test_b = test_with_dx[base_features].copy()
        X_test_b['confidence'] = test_with_dx['confidence']
        X_test_b['diagnosis_missing'] = test_with_dx['diagnosis_missing']
        X_test_b['diagnostic_class'] = test_with_dx['diagnostic_class'].astype(str)

        # Encode
        categorical_b = ['payment_method', 'failure_class', 'diagnostic_class']
        X_test_b_encoded = pd.get_dummies(X_test_b, columns=categorical_b, drop_first=True)

        # Align with Model B
        for col in self.model_b['features']:
            if col not in X_test_b_encoded.columns:
                X_test_b_encoded[col] = 0
        self.X_test_b = X_test_b_encoded[self.model_b['features']]

        print(f"  Model B features: {len(self.X_test_b.columns)}")

        # Store augmented test for Model B allocation
        self.test_with_dx = test_with_dx

        # Baseline features (just needs raw data)
        self.X_test_baseline = self.test_df.copy()

        print(f"  ✓ All test features constructed")

    def step_4_predictions(self):
        """Step 4: Generate predictions and calculate metrics."""
        print("\n" + "=" * 70)
        print("STEP 4: PREDICTIONS AND METRICS")
        print("=" * 70)

        y_true = self.test_df['target'].values

        # Baseline
        proba_baseline = self.baseline.predict_proba(self.X_test_baseline)
        metrics_baseline = self._calculate_metrics(y_true, proba_baseline, "Baseline")
        self.results['baseline'] = {'probabilities': proba_baseline, 'metrics': metrics_baseline}

        # Model A
        proba_a = self.model_a['model'].predict_proba(self.X_test_a)[:, 1]
        metrics_a = self._calculate_metrics(y_true, proba_a, "Model A")
        self.results['model_a'] = {'probabilities': proba_a, 'metrics': metrics_a}

        # Model B
        proba_b = self.model_b['model'].predict_proba(self.X_test_b)[:, 1]
        metrics_b = self._calculate_metrics(y_true, proba_b, "Model B")
        self.results['model_b'] = {'probabilities': proba_b, 'metrics': metrics_b}

    def _calculate_metrics(self, y_true, y_proba, name):
        """Calculate performance metrics."""
        metrics = {}

        # ROC-AUC
        metrics['roc_auc'] = roc_auc_score(y_true, y_proba)

        # PR-AUC
        precision, recall, _ = precision_recall_curve(y_true, y_proba)
        metrics['pr_auc'] = auc(recall, precision)

        # Brier
        metrics['brier_score'] = brier_score_loss(y_true, y_proba)

        # Log Loss
        metrics['log_loss'] = log_loss(y_true, y_proba)

        print(f"\n  {name}:")
        print(f"    ROC-AUC: {metrics['roc_auc']:.4f}")
        print(f"    PR-AUC: {metrics['pr_auc']:.4f}")
        print(f"    Brier: {metrics['brier_score']:.4f}")
        print(f"    Log Loss: {metrics['log_loss']:.4f}")

        return metrics

    def step_5_economic_allocation(self):
        """Step 5: Run economic allocation for all strategies."""
        print("\n" + "=" * 70)
        print("STEP 5: ECONOMIC ALLOCATION")
        print("=" * 70)

        # Baseline
        test_baseline_with_proba = self.test_df.copy()
        for col in self.X_test_a.columns:
            test_baseline_with_proba[col] = self.X_test_a[col].values
        test_baseline_with_proba['baseline_probability'] = self.results['baseline']['probabilities']

        baseline_provider = BaselineProbabilityProvider(self.baseline, test_baseline_with_proba)
        self.results['baseline']['allocation'] = self._run_allocation("Baseline", self.test_df, baseline_provider)

        # Model A
        test_a_with_proba = self.test_df.copy()
        for col in self.X_test_a.columns:
            test_a_with_proba[col] = self.X_test_a[col].values
        test_a_with_proba['model_a_probability'] = self.results['model_a']['probabilities']

        model_a_provider = ModelProbabilityProvider(
            self.model_a['model'],
            self.model_a['features'],
            test_a_with_proba
        )
        self.results['model_a']['allocation'] = self._run_allocation("Model A", self.test_df, model_a_provider)

        # Model B
        test_b_with_proba = self.test_df.copy()
        for col in self.X_test_b.columns:
            test_b_with_proba[col] = self.X_test_b[col].values
        test_b_with_proba['model_b_probability'] = self.results['model_b']['probabilities']

        model_b_provider = ModelProbabilityProvider(
            self.model_b['model'],
            self.model_b['features'],
            test_b_with_proba
        )
        self.results['model_b']['allocation'] = self._run_allocation("Model B", self.test_df, model_b_provider)

    def _run_allocation(self, strategy_name, test_df, probability_provider):
        """Run economic allocation for one strategy."""
        print(f"\n--- Running allocation: {strategy_name} ---")

        eligibility_provider = SimpleEligibilityProvider()

        optimizer = ConstrainedRecoveryOptimizer(
            prediction_provider=probability_provider,
            eligibility_provider=eligibility_provider,
            assumed_organic_recovery_rate=self.config.recovery.assumed_organic_recovery_rate,
            intervention_cost=float(self.config.costs.payment_link_intervention_cost),
            friction_cost=float(self.config.costs.customer_friction_cost_per_contact),
            risk_penalty=float(self.config.costs.risk_penalty),
        )

        all_selected = []
        total_predicted_ev = 0.0

        # Run per day
        for day in sorted(test_df['simulated_day'].unique()):
            day_opps = test_df[test_df['simulated_day'] == day]
            day_opps_dict = day_opps.to_dict('records')

            plan = optimizer.optimize_daily_opportunities(
                opportunities=day_opps_dict,
                merchant_id="MERCHANT_001",
                simulated_day=day,
                max_actions_per_day=self.config.recovery.max_actions_per_day,
            )

            for decision in plan.selected_actions:
                all_selected.append(decision.opportunity_id)
                total_predicted_ev += float(decision.incremental_ev)

        # Calculate realized outcomes
        if len(all_selected) == 0:
            selected_df = pd.DataFrame(columns=test_df.columns)
        else:
            selected_df = test_df[test_df['opportunity_id'].isin(all_selected)]

        realized_recovery_count = selected_df['target'].sum() if len(selected_df) > 0 else 0
        realized_recovery_rate = realized_recovery_count / len(selected_df) if len(selected_df) > 0 else 0.0
        realized_recovered_amount = selected_df[selected_df['target'] == 1]['amount'].sum() if len(selected_df) > 0 else 0.0
        realized_inr_per_action = realized_recovered_amount / len(selected_df) if len(selected_df) > 0 else 0.0

        results = {
            'strategy': strategy_name,
            'opportunities_evaluated': len(test_df),
            'actions_selected': len(all_selected),
            'action_rate': len(all_selected) / len(test_df),
            'predicted_net_ev': total_predicted_ev,
            'realized_recovery_count': int(realized_recovery_count),
            'realized_recovery_rate': float(realized_recovery_rate),
            'realized_recovered_amount': float(realized_recovered_amount),
            'realized_inr_per_action': float(realized_inr_per_action),
            'capacity_utilization': len(all_selected) / (self.config.recovery.max_actions_per_day * test_df['simulated_day'].nunique()),
            'selected_opportunity_ids': all_selected,  # Store for bootstrap
        }

        print(f"  Opportunities: {results['opportunities_evaluated']}")
        print(f"  Selected: {results['actions_selected']} ({results['action_rate']:.1%})")
        print(f"  Predicted Net EV: {results['predicted_net_ev']:.2f}")
        print(f"  Realized Recovery: {results['realized_recovery_count']}/{results['actions_selected']} ({results['realized_recovery_rate']:.1%})")
        print(f"  Realized Amount: {results['realized_recovered_amount']:.2f}")
        print(f"  Realized INR/Action: {results['realized_inr_per_action']:.2f}")

        return results

    def step_6_bootstrap_uncertainty(self):
        """Step 6: Calculate bootstrap uncertainty."""
        print("\n" + "=" * 70)
        print("STEP 6: BOOTSTRAP UNCERTAINTY")
        print("=" * 70)

        n_bootstrap = self.manifest['bootstrap_iterations']
        np.random.seed(self.manifest['bootstrap_random_seed'])

        print(f"\nRunning {n_bootstrap} bootstrap iterations...")

        # Get selected opportunity IDs for each strategy
        baseline_selected_ids = set(self.results['baseline']['allocation']['selected_opportunity_ids'])
        model_a_selected_ids = set(self.results['model_a']['allocation']['selected_opportunity_ids'])
        model_b_selected_ids = set(self.results['model_b']['allocation']['selected_opportunity_ids'])

        baseline_amounts = []
        model_a_amounts = []
        model_b_amounts = []
        model_a_vs_baseline = []
        model_b_vs_baseline = []

        for i in range(n_bootstrap):
            # Resample with replacement
            indices = np.random.choice(len(self.test_df), size=len(self.test_df), replace=True)
            boot_df = self.test_df.iloc[indices].reset_index(drop=True)

            # Calculate recovered amounts for each strategy
            # Filter by opportunity IDs that were selected
            baseline_boot = boot_df[boot_df['opportunity_id'].isin(baseline_selected_ids)]
            baseline_amt = baseline_boot[baseline_boot['target'] == 1]['amount'].sum()
            baseline_amounts.append(baseline_amt)

            model_a_boot = boot_df[boot_df['opportunity_id'].isin(model_a_selected_ids)]
            model_a_amt = model_a_boot[model_a_boot['target'] == 1]['amount'].sum()
            model_a_amounts.append(model_a_amt)

            model_b_boot = boot_df[boot_df['opportunity_id'].isin(model_b_selected_ids)]
            model_b_amt = model_b_boot[model_b_boot['target'] == 1]['amount'].sum()
            model_b_amounts.append(model_b_amt)

            # Deltas
            model_a_vs_baseline.append(model_a_amt - baseline_amt)
            model_b_vs_baseline.append(model_b_amt - baseline_amt)

        # Calculate 95% percentile intervals
        self.results['bootstrap'] = {
            'n_iterations': n_bootstrap,
            'random_seed': self.manifest['bootstrap_random_seed'],
            'baseline': {
                'point_estimate': self.results['baseline']['allocation']['realized_recovered_amount'],
                'bootstrap_mean': np.mean(baseline_amounts),
                'percentile_95_ci': [np.percentile(baseline_amounts, 2.5), np.percentile(baseline_amounts, 97.5)],
            },
            'model_a': {
                'point_estimate': self.results['model_a']['allocation']['realized_recovered_amount'],
                'bootstrap_mean': np.mean(model_a_amounts),
                'percentile_95_ci': [np.percentile(model_a_amounts, 2.5), np.percentile(model_a_amounts, 97.5)],
            },
            'model_b': {
                'point_estimate': self.results['model_b']['allocation']['realized_recovered_amount'],
                'bootstrap_mean': np.mean(model_b_amounts),
                'percentile_95_ci': [np.percentile(model_b_amounts, 2.5), np.percentile(model_b_amounts, 97.5)],
            },
            'model_a_vs_baseline': {
                'point_estimate': (
                    self.results['model_a']['allocation']['realized_recovered_amount'] -
                    self.results['baseline']['allocation']['realized_recovered_amount']
                ),
                'bootstrap_mean': np.mean(model_a_vs_baseline),
                'percentile_95_ci': [np.percentile(model_a_vs_baseline, 2.5), np.percentile(model_a_vs_baseline, 97.5)],
            },
            'model_b_vs_baseline': {
                'point_estimate': (
                    self.results['model_b']['allocation']['realized_recovered_amount'] -
                    self.results['baseline']['allocation']['realized_recovered_amount']
                ),
                'bootstrap_mean': np.mean(model_b_vs_baseline),
                'percentile_95_ci': [np.percentile(model_b_vs_baseline, 2.5), np.percentile(model_b_vs_baseline, 97.5)],
            },
        }

        print(f"\nBootstrap Results (95% CI):")
        print(f"  Baseline: {self.results['bootstrap']['baseline']['point_estimate']:.2f} INR")
        print(f"    95% CI: [{self.results['bootstrap']['baseline']['percentile_95_ci'][0]:.2f}, {self.results['bootstrap']['baseline']['percentile_95_ci'][1]:.2f}]")
        print(f"  Model A: {self.results['bootstrap']['model_a']['point_estimate']:.2f} INR")
        print(f"    95% CI: [{self.results['bootstrap']['model_a']['percentile_95_ci'][0]:.2f}, {self.results['bootstrap']['model_a']['percentile_95_ci'][1]:.2f}]")
        print(f"  Model B: {self.results['bootstrap']['model_b']['point_estimate']:.2f} INR")
        print(f"    95% CI: [{self.results['bootstrap']['model_b']['percentile_95_ci'][0]:.2f}, {self.results['bootstrap']['model_b']['percentile_95_ci'][1]:.2f}]")
        print(f"\n  Model A vs Baseline: {self.results['bootstrap']['model_a_vs_baseline']['point_estimate']:.2f} INR")
        print(f"    95% CI: [{self.results['bootstrap']['model_a_vs_baseline']['percentile_95_ci'][0]:.2f}, {self.results['bootstrap']['model_a_vs_baseline']['percentile_95_ci'][1]:.2f}]")
        print(f"  Model B vs Baseline: {self.results['bootstrap']['model_b_vs_baseline']['point_estimate']:.2f} INR")
        print(f"    95% CI: [{self.results['bootstrap']['model_b_vs_baseline']['percentile_95_ci'][0]:.2f}, {self.results['bootstrap']['model_b_vs_baseline']['percentile_95_ci'][1]:.2f}]")

    def step_7_calibration(self):
        """Step 7: Generate calibration curves."""
        print("\n" + "=" * 70)
        print("STEP 7: CALIBRATION CURVES")
        print("=" * 70)

        y_true = self.test_df['target'].values

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        for idx, (name, strategy) in enumerate([
            ('Baseline', 'baseline'),
            ('Model A', 'model_a'),
            ('Model B', 'model_b')
        ]):
            proba = self.results[strategy]['probabilities']

            # Calibration curve with appropriate bins for n=300
            n_bins = 10
            fraction_of_positives, mean_predicted_value = calibration_curve(
                y_true, proba, n_bins=n_bins, strategy='quantile'
            )

            ax = axes[idx]
            ax.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
            ax.plot(mean_predicted_value, fraction_of_positives, 's-', label=name)
            ax.set_xlabel('Mean Predicted Probability')
            ax.set_ylabel('Fraction of Positives')
            ax.set_title(f'{name} Calibration (n=300)')
            ax.legend()
            ax.grid(alpha=0.3)

        plt.tight_layout()
        output_path = self.output_dir / 'final-test-calibration.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"  ✓ Calibration curves saved to: {output_path}")

    def step_8_final_reports(self):
        """Step 8: Generate final reports."""
        print("\n" + "=" * 70)
        print("STEP 8: FINAL REPORTS")
        print("=" * 70)

        # JSON report
        report = {
            'manifest': self.manifest,
            'test_size': len(self.test_df),
            'test_accessed': True,
            'baseline': {
                'metrics': self.results['baseline']['metrics'],
                'allocation': self.results['baseline']['allocation'],
                'bootstrap': self.results['bootstrap']['baseline'],
            },
            'model_a': {
                'metrics': self.results['model_a']['metrics'],
                'allocation': self.results['model_a']['allocation'],
                'bootstrap': self.results['bootstrap']['model_a'],
            },
            'model_b': {
                'metrics': self.results['model_b']['metrics'],
                'allocation': self.results['model_b']['allocation'],
                'bootstrap': self.results['bootstrap']['model_b'],
            },
            'comparison': {
                'model_a_vs_baseline': self.results['bootstrap']['model_a_vs_baseline'],
                'model_b_vs_baseline': self.results['bootstrap']['model_b_vs_baseline'],
            },
        }

        json_path = self.output_dir / 'final-test-evaluation-v1.0.json'
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"  ✓ JSON report: {json_path}")

        # Markdown report
        md_path = self.output_dir / 'final-test-evaluation-v1.0.md'
        self._generate_markdown_report(report, md_path)
        print(f"  ✓ Markdown report: {md_path}")

    def _generate_markdown_report(self, report, output_path):
        """Generate markdown report."""
        with open(output_path, 'w') as f:
            f.write("# RAY V1.0 - Final Test Evaluation\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write("**Prompt**: 8\n")
            f.write("**Status**: TEST EVALUATION COMPLETE\n\n")
            f.write("---\n\n")

            f.write("## Executive Summary\n\n")
            f.write("This is the FIRST and ONLY frozen evaluation of the 300-case TEST set.\n\n")
            f.write(f"**Test Accessed**: {report['test_accessed']}\n\n")
            f.write("---\n\n")

            f.write("## Model Metrics (Test Set)\n\n")
            f.write("| Metric | Baseline | Model A | Model B |\n")
            f.write("|--------|----------|---------|----------|\n")
            f.write(f"| ROC-AUC | {report['baseline']['metrics']['roc_auc']:.4f} | {report['model_a']['metrics']['roc_auc']:.4f} | {report['model_b']['metrics']['roc_auc']:.4f} |\n")
            f.write(f"| PR-AUC | {report['baseline']['metrics']['pr_auc']:.4f} | {report['model_a']['metrics']['pr_auc']:.4f} | {report['model_b']['metrics']['pr_auc']:.4f} |\n")
            f.write(f"| Brier | {report['baseline']['metrics']['brier_score']:.4f} | {report['model_a']['metrics']['brier_score']:.4f} | {report['model_b']['metrics']['brier_score']:.4f} |\n")
            f.write(f"| Log Loss | {report['baseline']['metrics']['log_loss']:.4f} | {report['model_a']['metrics']['log_loss']:.4f} | {report['model_b']['metrics']['log_loss']:.4f} |\n\n")

            f.write("---\n\n")
            f.write("## Economic Results (Test Set)\n\n")
            f.write("| Metric | Baseline | Model A | Model B |\n")
            f.write("|--------|----------|---------|----------|\n")
            f.write(f"| Actions Selected | {report['baseline']['allocation']['actions_selected']} | {report['model_a']['allocation']['actions_selected']} | {report['model_b']['allocation']['actions_selected']} |\n")
            f.write(f"| Action Rate | {report['baseline']['allocation']['action_rate']:.1%} | {report['model_a']['allocation']['action_rate']:.1%} | {report['model_b']['allocation']['action_rate']:.1%} |\n")
            f.write(f"| Predicted Net EV | {report['baseline']['allocation']['predicted_net_ev']:.2f} | {report['model_a']['allocation']['predicted_net_ev']:.2f} | {report['model_b']['allocation']['predicted_net_ev']:.2f} |\n")
            f.write(f"| Realized Recovery | {report['baseline']['allocation']['realized_recovery_count']}/{report['baseline']['allocation']['actions_selected']} | {report['model_a']['allocation']['realized_recovery_count']}/{report['model_a']['allocation']['actions_selected']} | {report['model_b']['allocation']['realized_recovery_count']}/{report['model_b']['allocation']['actions_selected']} |\n")
            f.write(f"| Realized Amount | {report['baseline']['allocation']['realized_recovered_amount']:.2f} | {report['model_a']['allocation']['realized_recovered_amount']:.2f} | {report['model_b']['allocation']['realized_recovered_amount']:.2f} |\n")
            f.write(f"| INR/Action | {report['baseline']['allocation']['realized_inr_per_action']:.2f} | {report['model_a']['allocation']['realized_inr_per_action']:.2f} | {report['model_b']['allocation']['realized_inr_per_action']:.2f} |\n\n")

            f.write("---\n\n")
            f.write("**Generated**: {}\n".format(datetime.now().isoformat()))

    def run(self):
        """Run complete final test evaluation."""
        print("\n" + "=" * 70)
        print("RAY V1 - FINAL TEST EVALUATION (PROMPT 8)")
        print("=" * 70)
        print("\n⚠️  THIS IS THE FIRST AND ONLY FROZEN TEST EVALUATION")
        print("⚠️  300-CASE TEST SET WILL BE ACCESSED")
        print("\n" + "=" * 70)

        self.step_0_preregistration()
        self.step_1_load_test()
        self.step_2_load_frozen_artifacts()
        self.step_3_construct_test_features()
        self.step_4_predictions()
        self.step_5_economic_allocation()
        self.step_6_bootstrap_uncertainty()
        self.step_7_calibration()
        self.step_8_final_reports()

        print("\n" + "=" * 70)
        print("FINAL TEST EVALUATION COMPLETE")
        print("=" * 70)
        print(f"\nTEST_ACCESS = TRUE")
        print(f"This is the first and only frozen final evaluation of TEST v1.0.")


if __name__ == "__main__":
    evaluator = FinalTestEvaluator()
    evaluator.run()
