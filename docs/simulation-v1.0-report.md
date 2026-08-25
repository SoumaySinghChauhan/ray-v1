# RAY V1 Synthetic World Generation Report

## Dataset Version

- **Simulation Version**: 1.0.0
- **Dataset Version**: 1.0.0
- **Generation Date**: 2026-08-25
- **World Seed**: 42
- **Status**: **FROZEN**

## Overview

This report documents the synthetic world generated for RAY V1 evaluation.

**IMPORTANT**: All data is synthetic. Recovery rates, customer behavior, and economic results are not claims about production Razorpay merchant behavior.

## Generation Summary

| Metric | Value |
|--------|-------|
| Total Customers | 1,500 |
| Customers with Current Opportunity | 1,000 |
| Customers without Current Opportunity | 500 |
| Total Historical Transactions | 37,456 |
| Average Transactions per Customer | 25.0 |
| Current Opportunities | 1,000 |
| Simulated Days | 10 |

## Data Splits (By Customer)

| Split | Customers | Opportunities |
|-------|-----------|---------------|
| Train | 550 | 550 |
| Validation | 150 | 150 |
| Test | 300 | 300 |
| **Total** | **1,000** | **1,000** |

**Critical**: Each customer has exactly ONE current opportunity. No customer appears in multiple splits.

## Observable Distributions

### Failure Classes

Realistic distribution across failure types:

| Failure Class | Count | Percentage |
|---------------|-------|------------|
| Soft Decline | 448 | 44.8% |
| Hard Decline | 317 | 31.7% |
| Authentication Failure | 123 | 12.3% |
| Gateway Error | 67 | 6.7% |
| Unknown | 45 | 4.5% |

**Interpretation**: Soft declines (temporary issues like insufficient funds) are most common, matching realistic payment failure distributions.

### Payment Methods

| Method | Count | Percentage |
|--------|-------|------------|
| Card | 502 | 50.2% |
| UPI | 297 | 29.7% |
| Netbanking | 159 | 15.9% |
| Wallet | 42 | 4.2% |

### Payment Amount Distribution

| Statistic | Value (INR) |
|-----------|-------------|
| Count | 1,000 |
| Mean | ₹3,468.22 |
| Std Dev | ₹5,925.91 |
| Min | ₹65.12 |
| 25th Percentile | ₹794.87 |
| Median | ₹1,614.35 |
| 75th Percentile | ₹3,585.53 |
| Max | ₹72,241.84 |

**Interpretation**: Log-normal distribution with realistic heterogeneity. Median payment is ₹1,614, matching typical e-commerce transaction sizes. Long tail represents high-value transactions.

### Historical Recovery Rate Distribution

Customer-level historical recovery rates (from past payment failures):

| Statistic | Value |
|-----------|-------|
| Count | 1,000 |
| Mean | 0.290 (29.0%) |
| Std Dev | 0.238 |
| Min | 0.000 (0%) |
| 25th Percentile | 0.100 (10%) |
| Median | 0.257 (25.7%) |
| 75th Percentile | 0.429 (42.9%) |
| Max | 1.000 (100%) |

**Interpretation**: Wide heterogeneity in customer recovery behavior. Some customers (25th percentile) have only 10% historical recovery, while others (75th percentile) recover 43% of failures.

### Simulated Day Distribution

Perfect uniform distribution across 10 simulated days:

| Day | Opportunities |
|-----|---------------|
| 1-10 (each) | 100 |

**Interpretation**: 100 opportunities per simulated day allows realistic daily capacity constraints (default: 10 actions/day).

## Hidden Simulator Distributions

**WARNING**: The following distributions represent simulator ground truth. They are NEVER exposed to RAY's production decision logic.

### True Organic Recovery Probability

Natural recovery without intervention:

| Statistic | Value |
|-----------|-------|
| Count | 1,000 |
| Mean | 0.0186 (1.86%) |
| Std Dev | 0.0103 |
| Min | 0.010 (1.0%) |
| 25th Percentile | 0.010 (1.0%) |
| Median | 0.014 (1.4%) |
| 75th Percentile | 0.025 (2.5%) |
| Max | 0.064 (6.4%) |

**Interpretation**: Organic recovery (do_nothing) is generally low (mean 1.86%), representing the baseline of customers naturally resolving payment issues without intervention. Note that RAY *assumes* 4% organic recovery, which is higher than the true mean.

### True Payment Link Recovery Probability

Recovery with payment link intervention:

| Statistic | Value |
|-----------|-------|
| Count | 1,000 |
| Mean | 0.160 (16.0%) |
| Std Dev | 0.103 |
| Min | 0.050 (5.0%) |
| 25th Percentile | 0.081 (8.1%) |
| Median | 0.134 (13.4%) |
| 75th Percentile | 0.213 (21.3%) |
| Max | 0.622 (62.2%) |

**Interpretation**: Payment link intervention is substantially more effective than organic recovery (16.0% vs 1.86% mean). Wide heterogeneity exists - some opportunities have low recovery potential (5%) while others are highly recoverable (62%).

### Incremental Value of Payment Link

True incremental probability:

```
Mean Incremental = 16.0% - 1.86% = 14.14 percentage points
```

This represents the true average lift from payment link intervention vs doing nothing.

## Observable vs Hidden: What RAY Sees

### RAY Can See (Observable Features)

- Payment amount
- Payment method
- Failure class (soft_decline, hard_decline, etc.)
- Failure description (human-readable)
- Customer historical payment count
- Customer historical success count
- Customer historical failure count
- Customer historical recovery count
- Customer historical recovery rate
- Customer lifetime value
- Average payment amount
- Days since first payment
- Hours since current failure
- Retry count
- Contact count

### RAY Cannot See (Hidden Variables)

- True organic recovery probability
- True payment link recovery probability
- Customer payment reliability (latent trait)
- Customer recovery affinity (latent trait)
- Customer contact responsiveness (latent trait)
- Customer spending tier (latent)
- Customer maturity (latent)
- Scenario ID
- Hidden scenario parameters

**This separation is enforced by dataset structure and data loaders.**

## Ground Truth Probability Model

The true recovery probabilities are calculated from:

**Organic Recovery**:
- Base rate: 4% (configured assumption)
- Customer recovery affinity (hidden)
- Failure scenario modifier
- Payment amount factor
- Time decay

**Payment Link Recovery**:
- Base rate: 35%
- Customer payment reliability (hidden)
- Customer recovery affinity (hidden)
- Customer contact responsiveness (hidden)
- Failure scenario modifier
- Historical success factor
- Customer maturity factor
- Payment amount factor

Multiple factors contribute to final probabilities, creating realistic heterogeneity.

## Validation Results

All validation checks passed:

✓ Manifest exists  
✓ Observable opportunities (1,000)  
✓ Historical transactions (20-30 per customer)  
✓ Data splits (550/150/300)  
✓ Customer uniqueness (no duplicates)  
✓ Simulated days (10)  
✓ Failure classes (valid taxonomy)  
✓ Amount ranges (positive, within cap)  
✓ Hidden/observable separation (enforced)  
✓ Ground truth validity (probabilities in [0,1])  

## Reproducibility

- **World Seed**: 42
- **Dataset Split Seed**: 42
- **Generation**: Deterministic
- **Status**: Same seeds produce identical dataset

## File Structure

```
datasets/v1.0.0/
├── observable/
│   ├── customers.parquet (1,500 rows)
│   ├── historical_transactions.parquet (37,456 rows)
│   └── current_opportunities.parquet (1,000 rows)
├── hidden/
│   ├── customer_latent_state.parquet (1,500 rows - HIDDEN)
│   └── ground_truth_outcomes.parquet (1,000 rows - HIDDEN)
└── metadata/
    └── dataset_manifest.json
```

## Known Characteristics

### Design Decisions

1. **One opportunity per customer**: Simplifies customer-level split and prevents information leakage.

2. **10 simulated days**: Allows realistic daily capacity constraints without excessive computation.

3. **Historical recovery rate as baseline**: Simple, interpretable baseline that uses customer-specific history.

4. **Log-normal payment amounts**: Realistic distribution matching e-commerce patterns.

5. **Heterogeneous customers**: Multiple archetypes (reliable/new/frequent-failer/etc.) create realistic variation.

### Limitations

1. **Synthetic data**: Does not represent actual Razorpay merchant behavior.

2. **Single merchant**: All data is from one simulated merchant.

3. **Simplified payment methods**: Four categories may not capture full method diversity.

4. **No temporal trends**: Customer behavior is stationary (no seasonal effects, trends).

5. **No external factors**: No modeling of issuer-specific behavior, regional effects, or market conditions.

## Freeze Status

**SIMULATION PARAMETERS ARE NOW FROZEN.**

Any modifications to simulator parameters require:

1. Incrementing `simulation_version` (e.g., to 1.1.0)
2. Incrementing `dataset_version`
3. Documenting changes in `docs/decisions.md`
4. Regenerating complete dataset
5. Invalidating prior benchmark results
6. Re-running complete evaluation

**Do NOT modify simulator parameters after seeing RAY evaluation results.**

## Next Steps

This dataset is ready for:

1. **Prompt 2**: Offline LLM diagnosis (batch processing of failure descriptions)
2. **Prompt 3**: ML model training on train set, selection on validation set
3. **Prompt 4-5**: Optimizer and policy implementation
4. **Prompt 6**: Final evaluation on untouched test set

**Test set (300 customers) must remain untouched until final evaluation.**

---

*Dataset frozen: 2026-08-25*  
*Simulation version: 1.0.0*  
*Dataset version: 1.0.0*
