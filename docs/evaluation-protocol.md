# RAY Evaluation Protocol

## Overview

RAY V1 uses a synthetic benchmark to evaluate revenue recovery performance with strict experimental controls.

**Critical**: All benchmark data is SYNTHETIC. Results are not claims about production Razorpay behavior.

## Experimental Integrity Principles

### 1. Ground Truth Separation

The simulator contains hidden variables that represent true outcomes:
- True organic recovery probability
- True payment-link recovery probability
- Latent customer propensity
- Hidden scenario parameters

**RAY must NEVER access these variables during decision-making.**

Only observable information available at decision time may be used.

### 2. Offline LLM Diagnosis

LLM diagnosis is run ONCE offline and cached as part of dataset generation.

The benchmark uses cached diagnosis results.

**No live LLM calls during final benchmark execution.**

This ensures:
- Reproducibility
- Cost control
- No diagnosis variance between runs

### 3. Simulator Freeze

Simulator parameters must be frozen before final evaluation.

Process:
1. Build simulator
2. Inspect generated scenarios
3. Validate distributions
4. **FREEZE** parameters
5. Assign `simulation_version`
6. Generate benchmark dataset
7. Run evaluation

**If simulator parameters change after freeze**:
- Increment `simulation_version`
- Document change in `docs/decisions.md`
- Invalidate affected benchmark results
- Re-run complete evaluation

Never silently tune simulator to improve RAY's results.

## Data Generation

### Synthetic World

- **Total customers**: 1,500
- **Historical transactions per customer**: 20-30
- **Current opportunities**: 1,000 (one per customer)
- **Remaining customers**: 500 (no current opportunity)

### Customer-Level Split

Split is by CUSTOMER, not by opportunity:

- **Train**: 550 customers → 550 opportunities
- **Validation**: 150 customers → 150 opportunities
- **Test**: 300 customers → 300 opportunities

**Critical**: One current opportunity per customer ensures customer-level split equals opportunity-level split.

### Temporal Simulation

Test opportunities span:

**10 simulated calendar days**

Optimizer operates independently for each day with daily capacity reset.

**Default daily capacity**: 10 actions per day

This tests constrained sequential decision-making, not flat batch optimization.

## Training Set (550 opportunities)

**Purpose**: Model training and feature engineering

**Allowed uses**:
- Feature selection
- ML model training
- Feature engineering decisions

**Prohibited uses**:
- Final performance claims
- Hyperparameter selection (use validation)
- Threshold selection (use validation)

## Validation Set (150 opportunities)

**Purpose**: Model selection and hyperparameter tuning

**Allowed uses**:
- Logistic Regression vs LightGBM/XGBoost selection
- Hyperparameter tuning
- Calibration method selection
- Baseline threshold selection
- Configuration choices explicitly designated as validation-tuned

**Prohibited uses**:
- Model training
- Final performance claims

## Test Set (300 opportunities)

**Purpose**: Final performance evaluation

**MUST NOT be used until**:
- Model selection is complete
- Hyperparameters are frozen
- Baseline threshold is frozen
- Evaluation protocol is finalized

**Allowed uses** (ONE TIME):
- Final RAY performance evaluation
- Final baseline performance evaluation
- Bootstrap confidence interval calculation

**Prohibited uses**:
- Feature selection
- Model selection
- Hyperparameter tuning
- Threshold tuning
- Simulator parameter tuning
- Policy parameter tuning
- Debugging individual cases
- Any form of optimization

**If test set is used for tuning**:
- Results are scientifically invalid
- Must discard test set
- Must generate new held-out data

## Baseline

### Baseline Definition

```python
baseline_probability = customer_historical_recovery_rate
baseline_score = baseline_probability × payment_amount
```

For cold-start customers (zero historical failures):
```python
baseline_cold_start_probability = mean(validation_historical_recovery_rates)
```

**Critical**: Baseline estimates payment-link effectiveness, NOT organic recovery.

### Baseline Threshold Selection

1. Calculate baseline scores for all validation opportunities
2. For each candidate threshold:
   - Remove opportunities below threshold
   - Sort remaining by score descending
   - Select top N per day (N = daily capacity)
   - Execute payment_link for selected
   - Calculate net expected recovery
3. Select threshold that maximizes validation performance
4. **FREEZE** threshold
5. Apply frozen threshold to test set

Baseline threshold is selected ONCE on validation set.

**Never re-tune threshold using test results.**

## RAY Configuration

### Do-Nothing Assumption

RAY assumes:
```python
organic_recovery_rate = 0.04  # 4%
```

This is RAY's VISIBLE estimate, not ground truth.

RAY calculates:
```python
EV(do_nothing) = 0.04 × recoverable_amount
```

### Economic Calculation

For payment_link:
```python
gross_expected_recovery = P_ML(recovery) × amount
net_expected_recovery = gross_expected_recovery - costs

incremental_EV = EV(payment_link) - EV(do_nothing)
```

V1 costs (all configurable):
- `payment_link_intervention_cost`: 0 INR (default)
- `customer_friction_cost_per_contact`: 5 INR (default)

### Capacity Constraints

RAY operates under same constraints as baseline:
- `max_actions_per_day`: 10
- Simulated days: 10
- Total possible actions: 100

Both systems must allocate limited capacity optimally.

## Evaluation Metrics

### Primary Metric

**Incremental Recovery**:

```
RAY_incremental = RAY_recovered - baseline_recovered
```

Measured in INR (or configured currency).

### Uncertainty Quantification

95% bootstrap confidence interval:

1. Resample test opportunities 1,000 times with replacement
2. Calculate incremental recovery for each resample
3. Report 2.5th and 97.5th percentiles

Bootstrap seed: `bootstrap_seed = 45`

### Secondary Metrics

- Total actions taken
- Actions per day
- Average incremental value per action
- Precision @ top-K opportunities
- Calibration error (if applicable)

## Ground Truth Outcomes

Simulator generates outcomes independently:

```python
# Simulator internal logic (RAY cannot access)
if action == "payment_link":
    recovered = random() < true_payment_link_probability
elif action == "do_nothing":
    recovered = random() < true_organic_probability
```

RAY never sees:
- `true_payment_link_probability`
- `true_organic_probability`

ML model predicts simulator outcomes.

Model does not define its own labels.

## Execution Protocol

### Step 1: Dataset Generation

```bash
python simulator/generation/generate_world.py \
  --simulation-version 1.0.0 \
  --output datasets/v1.0.0/
```

Creates:
- Customer histories
- Current opportunities
- Ground truth parameters (hidden)

### Step 2: LLM Diagnosis (Offline)

```bash
python ai/diagnosis/batch_diagnose.py \
  --input datasets/v1.0.0/opportunities.jsonl \
  --output datasets/v1.0.0/diagnoses.jsonl \
  --model claude-3-5-sonnet-20241022
```

Cached diagnosis includes:
- `diagnosis_model_version`
- `diagnosis_prompt_version`
- `diagnosis_timestamp`

### Step 3: Feature Engineering

```bash
python ml/features/engineer_features.py \
  --input datasets/v1.0.0/ \
  --output datasets/v1.0.0/features/
```

Generates observable feature set.

### Step 4: Train/Val/Test Split

```bash
python simulator/generation/split_data.py \
  --input datasets/v1.0.0/features/ \
  --output datasets/v1.0.0/splits/ \
  --train 550 --val 150 --test 300 \
  --seed 42
```

### Step 5: Model Training

```bash
python ml/training/train_model.py \
  --train datasets/v1.0.0/splits/train.parquet \
  --model-type logistic \
  --output ml/models/v1.0.0/
```

### Step 6: Hyperparameter Selection (Validation)

```bash
python ml/training/tune_hyperparameters.py \
  --train datasets/v1.0.0/splits/train.parquet \
  --val datasets/v1.0.0/splits/val.parquet \
  --output ml/models/v1.0.0/best_config.json
```

### Step 7: Baseline Threshold Selection (Validation)

```bash
python evaluation/baselines/tune_baseline.py \
  --val datasets/v1.0.0/splits/val.parquet \
  --output evaluation/baselines/v1.0.0_threshold.json
```

### Step 8: Final Evaluation (Test - ONE TIME)

```bash
python evaluation/benchmark/run_final_eval.py \
  --test datasets/v1.0.0/splits/test.parquet \
  --model ml/models/v1.0.0/final_model.pkl \
  --baseline-threshold evaluation/baselines/v1.0.0_threshold.json \
  --output evaluation/benchmark/results/v1.0.0.json
```

Produces:
- RAY incremental recovery
- Baseline performance
- Bootstrap confidence intervals
- Full decision audit trail

## Reproducibility

### Random Seeds

```python
world_seed = 42          # Synthetic world generation
training_seed = 43       # ML model training
evaluation_seed = 44     # Test set evaluation
bootstrap_seed = 45      # Bootstrap resampling
```

### Version Tracking

Every evaluation result must record:

```json
{
  "simulation_version": "1.0.0",
  "dataset_version": "1.0.0",
  "diagnosis_prompt_version": "1.0.0",
  "diagnosis_model_version": "claude-3-5-sonnet-20241022",
  "model_version": "1.0.0",
  "optimizer_version": "1.0.0",
  "policy_version": "1.0.0",
  "evaluation_protocol_version": "1.0.0"
}
```

## Validity Checks

Before trusting results, verify:

1. **No test set leakage**
   - Test opportunities never seen during training
   - Test customer IDs not in train/val

2. **Ground truth isolation**
   - Production code has no imports from `simulator/ground_truth/`
   - Hidden variables never logged or exposed

3. **Frozen parameters**
   - Simulator version matches dataset
   - No post-freeze parameter changes

4. **Reproducibility**
   - Same seeds produce same results
   - Cached LLM diagnoses are deterministic

5. **Capacity constraints**
   - Both RAY and baseline respect daily limits
   - No system exceeds 10 actions per simulated day

## Reporting Standards

### Minimal Report

```
RAY V1 Evaluation Results

Dataset: v1.0.0 (300 test opportunities, 10 simulated days)
Capacity: 10 actions/day

RAY Incremental Recovery: ₹X,XXX (95% CI: [₹Y,YYY, ₹Z,ZZZ])
Actions Taken: N / 100 possible

Baseline: Historical recovery rate + threshold @ validation
RAY: ML recovery prediction + economic optimization

All data is SYNTHETIC. Results are not claims about production behavior.

Version Details: [table of all version numbers]
```

### Never Report

- Individual customer results
- Single-day cherry-picked performance
- Results before confidence intervals
- Claims that results generalize to production
- Tuned-on-test results as valid

## Experimental Modifications

To change evaluation protocol:

1. Document change in `docs/decisions.md`
2. Increment `evaluation_protocol_version`
3. Re-run complete pipeline from dataset generation
4. Report both old and new protocol results separately

Never:
- Silently change protocol mid-evaluation
- Report results without version tracking
- Mix results from different protocol versions
