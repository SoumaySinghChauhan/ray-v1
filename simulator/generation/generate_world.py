#!/usr/bin/env python3
"""
Synthetic world generation script.

Generates frozen dataset for RAY V1 evaluation.

CRITICAL: This script generates BOTH observable and hidden data.
They are exported to separate files and MUST remain separated.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
from datetime import datetime, timezone
from decimal import Decimal
import pandas as pd
import numpy as np
from typing import Any

from config import get_config
from simulator.world_model.customer_behavior import CustomerBehaviorModel
from simulator.scenarios.failure_scenarios import FailureScenarioGenerator
from simulator.generation.historical_transactions import HistoricalTransactionGenerator
from simulator.generation.opportunities import OpportunityGenerator
from simulator.ground_truth.probability_model import GroundTruthProbabilityModel


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class SyntheticWorldGenerator:
    """Generate complete synthetic world with hidden ground truth."""

    def __init__(self, output_dir: Path):
        """Initialize generator with configuration."""
        self.config = get_config()
        self.output_dir = output_dir
        self.merchant_id = "merchant_demo_001"

        # Base timestamp for simulation
        self.base_timestamp = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Initialize generators with reproducible seeds
        self.behavior_model = CustomerBehaviorModel(
            seed=self.config.reproducibility.world_seed
        )
        self.scenario_generator = FailureScenarioGenerator(
            seed=self.config.reproducibility.world_seed + 10
        )
        self.transaction_generator = HistoricalTransactionGenerator(
            seed=self.config.reproducibility.world_seed + 20,
            config=self.config,
            behavior_model=self.behavior_model,
        )
        self.opportunity_generator = OpportunityGenerator(
            seed=self.config.reproducibility.world_seed + 30,
            config=self.config,
            behavior_model=self.behavior_model,
            scenario_generator=self.scenario_generator,
        )
        self.ground_truth_model = GroundTruthProbabilityModel(
            seed=self.config.reproducibility.world_seed + 40,
            config=self.config,
        )

        # Create output directories
        (self.output_dir / "observable").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "hidden").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "metadata").mkdir(parents=True, exist_ok=True)

    def generate(self):
        """Generate complete synthetic world."""

        print("=" * 70)
        print("RAY V1 SYNTHETIC WORLD GENERATION")
        print("=" * 70)
        print(f"Simulation version: {self.config.versions.simulation_version}")
        print(f"Dataset version: {self.config.versions.dataset_version}")
        print(f"World seed: {self.config.reproducibility.world_seed}")
        print(f"Output: {self.output_dir}")
        print()

        # ====================================================================
        # STEP 1: Generate customers
        # ====================================================================

        print("Step 1: Generating customers...")
        customers = self.behavior_model.generate_customers(
            self.config.simulator.total_customers
        )
        print(f"  ✓ Generated {len(customers)} customers")
        print()

        # ====================================================================
        # STEP 2: Generate historical transactions
        # ====================================================================

        print("Step 2: Generating historical transactions...")
        all_transactions = []
        customer_histories = {}

        for i, customer in enumerate(customers):
            if (i + 1) % 500 == 0:
                print(f"  ... processed {i + 1}/{len(customers)} customers")

            transactions = self.transaction_generator.generate_history(
                customer,
                self.merchant_id,
                self.base_timestamp,
            )
            all_transactions.extend(transactions)
            customer_histories[customer.customer_id] = transactions

        print(f"  ✓ Generated {len(all_transactions)} historical transactions")
        print(f"    Average per customer: {len(all_transactions) / len(customers):.1f}")
        print()

        # ====================================================================
        # STEP 3: Select customers for current opportunities
        # ====================================================================

        print("Step 3: Selecting customers for current opportunities...")

        # Select exactly 1,000 customers for opportunities
        rng = np.random.RandomState(self.config.reproducibility.world_seed + 50)
        opportunity_customers = rng.choice(
            customers,
            size=self.config.simulator.current_opportunities,
            replace=False,
        )

        print(f"  ✓ Selected {len(opportunity_customers)} customers")
        print(f"    Remaining {len(customers) - len(opportunity_customers)} have no current opportunity")
        print()

        # ====================================================================
        # STEP 4: Generate current opportunities with simulated days
        # ====================================================================

        print("Step 4: Generating current opportunities...")

        opportunities = []
        hidden_scenarios = []

        # Distribute opportunities across simulated days
        simulation_days = self.config.simulator.simulation_days
        opportunities_per_day = len(opportunity_customers) // simulation_days

        opportunity_idx = 0

        for day in range(1, simulation_days + 1):
            # Number of opportunities for this day
            if day < simulation_days:
                day_count = opportunities_per_day
            else:
                # Last day gets remainder
                day_count = len(opportunity_customers) - opportunity_idx

            for _ in range(day_count):
                customer = opportunity_customers[opportunity_idx]
                history = customer_histories[customer.customer_id]

                opportunity, scenario = self.opportunity_generator.generate_opportunity(
                    opportunity_idx=opportunity_idx,
                    customer=customer,
                    merchant_id=self.merchant_id,
                    historical_transactions=history,
                    simulated_day=day,
                    base_timestamp=self.base_timestamp,
                )

                opportunities.append(opportunity)
                hidden_scenarios.append((opportunity, scenario))
                opportunity_idx += 1

        print(f"  ✓ Generated {len(opportunities)} current opportunities")
        print(f"    Distributed across {simulation_days} simulated days")
        print()

        # ====================================================================
        # STEP 5: Assign train/validation/test splits
        # ====================================================================

        print("Step 5: Assigning data splits...")

        opportunities = self.opportunity_generator.assign_splits(
            opportunities,
            split_seed=self.config.reproducibility.world_seed,
        )

        train_count = sum(1 for o in opportunities if o.split == "train")
        val_count = sum(1 for o in opportunities if o.split == "validation")
        test_count = sum(1 for o in opportunities if o.split == "test")

        print(f"  ✓ Train: {train_count}")
        print(f"  ✓ Validation: {val_count}")
        print(f"  ✓ Test: {test_count}")
        print()

        # ====================================================================
        # STEP 6: Calculate ground truth (HIDDEN)
        # ====================================================================

        print("Step 6: Calculating hidden ground truth...")

        ground_truths = []

        for opportunity, scenario in hidden_scenarios:
            # Find customer latent state
            customer = next(c for c in customers if c.customer_id == opportunity.customer_id)

            # Calculate true probabilities
            ground_truth = self.ground_truth_model.calculate_ground_truth(
                opportunity_id=opportunity.opportunity_id,
                customer=customer,
                scenario=scenario,
                amount=opportunity.amount,
                hours_since_failure=opportunity.hours_since_failure,
                historical_recovery_rate=opportunity.historical_recovery_rate,
                historical_payment_count=opportunity.historical_payment_count,
            )

            ground_truths.append(ground_truth)

        print(f"  ✓ Calculated ground truth for {len(ground_truths)} opportunities")
        print()

        # ====================================================================
        # STEP 7: Export datasets
        # ====================================================================

        print("Step 7: Exporting datasets...")

        self._export_customers(customers)
        self._export_historical_transactions(all_transactions)
        self._export_current_opportunities(opportunities)
        self._export_ground_truth(customers, ground_truths)
        self._export_metadata(
            customers,
            all_transactions,
            opportunities,
            ground_truths,
        )

        print()
        print("=" * 70)
        print("GENERATION COMPLETE")
        print("=" * 70)

    def _export_customers(self, customers):
        """Export customer observable data only."""

        # OBSERVABLE: derived from history only, no latent traits
        customer_data = []
        for customer in customers:
            customer_data.append({
                "customer_id": customer.customer_id,
                "merchant_id": self.merchant_id,
                # DO NOT export hidden traits
            })

        df = pd.DataFrame(customer_data)
        output_path = self.output_dir / "observable" / "customers.parquet"
        df.to_parquet(output_path, index=False)
        print(f"  ✓ Exported {len(df)} customers (observable)")

    def _export_historical_transactions(self, transactions):
        """Export historical transaction data."""

        transaction_data = []
        for t in transactions:
            transaction_data.append({
                "transaction_id": t.transaction_id,
                "customer_id": t.customer_id,
                "merchant_id": t.merchant_id,
                "amount": float(t.amount),
                "currency": t.currency,
                "payment_method": t.payment_method,
                "status": t.status,
                "failure_class": t.failure_class,
                "failure_description": t.failure_description,
                "created_at": t.created_at,
                "recovered_at": t.recovered_at,
                "was_recovered": t.was_recovered,
            })

        df = pd.DataFrame(transaction_data)
        output_path = self.output_dir / "observable" / "historical_transactions.parquet"
        df.to_parquet(output_path, index=False)
        print(f"  ✓ Exported {len(df)} historical transactions")

    def _export_current_opportunities(self, opportunities):
        """Export current opportunity observable data."""

        opportunity_data = []
        for o in opportunities:
            opportunity_data.append({
                "opportunity_id": o.opportunity_id,
                "customer_id": o.customer_id,
                "merchant_id": o.merchant_id,
                "payment_id": o.payment_id,
                "amount": float(o.amount),
                "currency": o.currency,
                "payment_method": o.payment_method,
                "failure_class": o.failure_class,
                "failure_description": o.failure_description,
                "created_at": o.created_at,
                "hours_since_failure": o.hours_since_failure,
                "simulated_day": o.simulated_day,
                "retry_count": o.retry_count,
                "contact_count": o.contact_count,
                "historical_payment_count": o.historical_payment_count,
                "historical_success_count": o.historical_success_count,
                "historical_failure_count": o.historical_failure_count,
                "historical_recovery_count": o.historical_recovery_count,
                "historical_recovery_rate": o.historical_recovery_rate,
                "customer_lifetime_value": float(o.customer_lifetime_value),
                "avg_payment_amount": float(o.avg_payment_amount),
                "days_since_first_payment": o.days_since_first_payment,
                "split": o.split,
            })

        df = pd.DataFrame(opportunity_data)
        output_path = self.output_dir / "observable" / "current_opportunities.parquet"
        df.to_parquet(output_path, index=False)
        print(f"  ✓ Exported {len(df)} current opportunities (observable)")

    def _export_ground_truth(self, customers, ground_truths):
        """Export HIDDEN ground truth data."""

        # Customer latent states (HIDDEN)
        customer_latent_data = []
        for customer in customers:
            customer_latent_data.append({
                "customer_id": customer.customer_id,
                "payment_reliability": customer.payment_reliability,
                "recovery_affinity": customer.recovery_affinity,
                "contact_responsiveness": customer.contact_responsiveness,
                "spending_tier": customer.spending_tier,
                "customer_maturity": customer.customer_maturity,
            })

        df_customers = pd.DataFrame(customer_latent_data)
        output_path = self.output_dir / "hidden" / "customer_latent_state.parquet"
        df_customers.to_parquet(output_path, index=False)
        print(f"  ✓ Exported {len(df_customers)} customer latent states (HIDDEN)")

        # Ground truth probabilities (HIDDEN)
        ground_truth_data = []
        for gt in ground_truths:
            ground_truth_data.append({
                "opportunity_id": gt.opportunity_id,
                "true_organic_recovery_probability": gt.true_organic_recovery_probability,
                "true_payment_link_recovery_probability": gt.true_payment_link_recovery_probability,
                "scenario_id": gt.scenario_id,
                "scenario_failure_class": gt.scenario_failure_class,
                "customer_payment_reliability": gt.customer_payment_reliability,
                "customer_recovery_affinity": gt.customer_recovery_affinity,
                "customer_contact_responsiveness": gt.customer_contact_responsiveness,
            })

        df_truth = pd.DataFrame(ground_truth_data)
        output_path = self.output_dir / "hidden" / "ground_truth_outcomes.parquet"
        df_truth.to_parquet(output_path, index=False)
        print(f"  ✓ Exported {len(df_truth)} ground truth outcomes (HIDDEN)")

    def _export_metadata(self, customers, transactions, opportunities, ground_truths):
        """Export dataset manifest and metadata."""

        manifest = {
            "dataset_version": self.config.versions.dataset_version,
            "simulation_version": self.config.versions.simulation_version,
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "world_seed": self.config.reproducibility.world_seed,
            "dataset_split_seed": self.config.reproducibility.world_seed,
            "customer_count": len(customers),
            "current_opportunity_count": len(opportunities),
            "historical_transaction_count": len(transactions),
            "simulation_day_count": self.config.simulator.simulation_days,
            "train_count": sum(1 for o in opportunities if o.split == "train"),
            "validation_count": sum(1 for o in opportunities if o.split == "validation"),
            "test_count": sum(1 for o in opportunities if o.split == "test"),
        }

        output_path = self.output_dir / "metadata" / "dataset_manifest.json"
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2, cls=DecimalEncoder)
        print(f"  ✓ Exported dataset manifest")


def main():
    """Main entry point."""

    output_dir = Path("datasets/v1.0.0")

    print()
    generator = SyntheticWorldGenerator(output_dir)
    generator.generate()
    print()
    print(f"Dataset ready at: {output_dir.absolute()}")
    print()


if __name__ == "__main__":
    main()
