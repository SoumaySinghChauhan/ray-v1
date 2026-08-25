# RAY Data Contract

## Observable vs Hidden Variables

### Observable Features (ALLOWED for RAY)

Features that would be available at decision time in a real system:

#### Payment Information
- `payment_amount`: Transaction amount (INR)
- `payment_method`: Payment method used
- `failure_reason`: Razorpay failure reason
- `failure_code`: Razorpay failure code
- `hours_since_failure`: Time elapsed since failure

#### Customer History
- `historical_payment_count`: Total historical payments
- `historical_success_count`: Historical successful payments
- `historical_failure_count`: Historical failed payments
- `historical_recovery_count`: Historical recoveries
- `historical_recovery_rate`: Historical success rate for recoveries
- `customer_lifetime_value`: Total historical transaction value
- `avg_payment_amount`: Average historical payment amount
- `days_since_first_payment`: Customer tenure

#### Recovery Attempt History
- `retry_count`: Number of recovery attempts for this payment
- `contact_count_last_30d`: Recent contact frequency
- `last_contact_days_ago`: Days since last contact

#### Contextual Features
- `day_of_week`: Day of week
- `hour_of_day`: Hour of day
- `is_weekend`: Weekend indicator
- `is_business_hours`: Business hours indicator

#### LLM Diagnosis (Cached)
- `failure_class`: Structured failure classification
- `diagnosis_confidence`: LLM confidence score
- `reason_codes`: Extracted reason codes

### Hidden Variables (FORBIDDEN for RAY)

Variables that exist only in the simulator and represent ground truth:

#### Simulator Ground Truth
- `true_organic_recovery_probability`: True P(recover | do_nothing)
- `true_payment_link_recovery_probability`: True P(recover | payment_link)
- `latent_customer_propensity`: Hidden customer trait
- `latent_issuer_behavior`: Hidden issuer policy
- `scenario_id`: Hidden scenario identifier
- `scenario_parameters`: Hidden scenario configuration

#### Future Information
- `actual_outcome`: Whether recovery actually happened (known only AFTER decision)
- `recovery_timestamp`: When recovery occurred (future)
- `recovery_amount`: Actual recovered amount (future)

#### Test Set Information
- `is_test_set`: Whether opportunity is in test set (evaluation only)
- `test_opportunity_index`: Position in test set (evaluation only)

**CRITICAL**: Production code must NEVER import or access hidden variables.

## Feature Engineering Rules

### Allowed Transformations

```python
# ALLOWED: Transformations of observable features
log_amount = np.log1p(payment_amount)
recovery_rate_smoothed = (historical_recovery_count + 1) / (historical_failure_count + 2)
time_decay_weight = np.exp(-hours_since_failure / 24)
```

### Prohibited Transformations

```python
# FORBIDDEN: Using future outcomes
recovery_success_indicator = int(actual_outcome == "recovered")

# FORBIDDEN: Using hidden variables
customer_true_propensity = latent_customer_propensity

# FORBIDDEN: Using test set membership
is_hard_case = is_test_set and scenario_id == "difficult"
```

## Dataset Structure

### Historical Transactions

Each customer has 20-30 historical transactions:

```json
{
  "customer_id": "cust_xxxxx",
  "transaction_id": "txn_xxxxx",
  "amount": 1500.00,
  "status": "success",
  "payment_method": "card",
  "timestamp": "2026-01-15T10:30:00Z",
  "failure_reason": null
}
```

Historical transactions must be temporally consistent:
- All historical transactions precede current opportunity
- Transactions ordered chronologically
- No future information leakage

### Current Opportunities

Each opportunity represents a failed payment:

```json
{
  "opportunity_id": "opp_xxxxx",
  "customer_id": "cust_xxxxx",
  "payment_id": "pay_xxxxx",
  "recoverable_amount": 2500.00,
  "failure_reason": "insufficient_funds",
  "failure_code": "BAD_REQUEST_ERROR",
  "created_at": "2026-02-10T14:20:00Z",
  "simulated_day": 3
}
```

### Cached LLM Diagnosis

```json
{
  "opportunity_id": "opp_xxxxx",
  "failure_class": "soft_decline",
  "confidence": 0.85,
  "reason_codes": ["insufficient_funds", "temporary"],
  "explanation": "Temporary insufficient funds, high recovery probability",
  "diagnosis_model_version": "claude-3-5-sonnet-20241022",
  "diagnosis_prompt_version": "1.0.0",
  "diagnosis_timestamp": "2026-02-01T09:00:00Z"
}
```

### Ground Truth (Simulator Internal)

```json
{
  "opportunity_id": "opp_xxxxx",
  "true_organic_probability": 0.15,
  "true_payment_link_probability": 0.45,
  "latent_customer_propensity": 0.6,
  "scenario_id": "temp_insufficient_funds",
  "scenario_params": {"issuer_retry_window_hours": 72}
}
```

**This structure is NEVER exposed to RAY.**

## Data Validation

### Training Data Validation

Before model training:

```python
assert all(df['payment_amount'] > 0)
assert all((df['historical_recovery_rate'] >= 0) & 
           (df['historical_recovery_rate'] <= 1))
assert all(df['hours_since_failure'] >= 0)
assert 'true_organic_probability' not in df.columns
assert 'actual_outcome' not in df.columns
```

### Test Data Validation

Before final evaluation:

```python
# Verify no train/val customers in test set
assert len(set(train_customers) & set(test_customers)) == 0

# Verify temporal consistency
assert all(test_df['created_at'] >= train_df['created_at'].max())

# Verify simulated days
assert test_df['simulated_day'].min() == 1
assert test_df['simulated_day'].max() == 10

# Verify no hidden variables leaked
prohibited_columns = [
    'true_organic_probability',
    'true_payment_link_probability', 
    'latent_customer_propensity',
    'scenario_id'
]
assert all(col not in test_df.columns for col in prohibited_columns)
```

## Feature Documentation

Every feature must be documented with:

```python
FEATURE_DEFINITIONS = {
    "payment_amount": {
        "type": "numeric",
        "description": "Payment amount in INR",
        "source": "payment.amount",
        "observability": "observable_at_decision_time",
        "nullable": False,
    },
    "historical_recovery_rate": {
        "type": "numeric",
        "description": "Customer's historical recovery rate",
        "source": "customer_history",
        "observability": "observable_at_decision_time",
        "nullable": False,
        "range": [0.0, 1.0],
        "cold_start": "use_validation_mean"
    },
}
```

## Label Definition

The ML target label is:

```python
# For payment_link action
label = int(actual_recovery_occurred_within_7_days)

# Binary classification
# 1 = recovered
# 0 = not recovered
```

Labels come from:
- **Training**: Simulator-generated outcomes
- **Production**: Actual Razorpay payment state

Labels are ONLY available AFTER decision execution.

Labels must NEVER be features.

## Missing Data Handling

### Cold Start Customers

Customers with no historical failures:

```python
if customer.historical_failure_count == 0:
    historical_recovery_rate = COLD_START_FALLBACK
    # Calculated from validation set mean
```

### Missing Optional Fields

```python
# Allowed: Imputation with explicit marker
if payment_method is None:
    payment_method = "unknown"
    payment_method_missing_flag = True
```

## Data Storage

### File Formats

- Historical data: Parquet (columnar, efficient)
- Streaming events: JSONL (line-delimited JSON)
- Configuration: JSON
- Results: JSON with metadata

### Directory Structure

```
datasets/
├── v1.0.0/
│   ├── customers.parquet
│   ├── historical_transactions.parquet
│   ├── opportunities.jsonl
│   ├── diagnoses.jsonl
│   ├── ground_truth/  # NEVER imported by production code
│   │   └── simulator_state.pkl
│   └── splits/
│       ├── train.parquet
│       ├── val.parquet
│       └── test.parquet  # Do not touch until final eval
```

## Data Immutability

Once a dataset version is created:

**DO NOT**:
- Modify historical transactions
- Re-diagnose opportunities with different LLM
- Change ground truth parameters
- Rebalance splits

**Instead**:
- Increment dataset version
- Document changes
- Regenerate complete dataset

## Privacy & Synthetic Data

V1 uses fully synthetic data:
- No real customer information
- No real payment data
- No PII

All data is generated by simulator.

Production system (future) would need:
- PII protection
- Data encryption
- Access controls
- Audit logging

But V1 benchmark has no privacy concerns because all data is synthetic.

## Data Quality Checks

Automated checks run before model training:

```python
def validate_dataset(df: pd.DataFrame) -> None:
    """Validate dataset meets contract requirements."""
    
    # Check required columns
    required = [
        'opportunity_id', 'customer_id', 'payment_amount',
        'historical_recovery_rate', 'hours_since_failure'
    ]
    assert all(col in df.columns for col in required)
    
    # Check no hidden variables
    hidden = [
        'true_organic_probability', 
        'true_payment_link_probability',
        'latent_customer_propensity'
    ]
    assert all(col not in df.columns for col in hidden)
    
    # Check value ranges
    assert (df['payment_amount'] > 0).all()
    assert (df['historical_recovery_rate'] >= 0).all()
    assert (df['historical_recovery_rate'] <= 1).all()
    
    # Check no future data leakage
    assert 'actual_outcome' not in df.columns
    assert 'recovery_timestamp' not in df.columns
```

## Summary

The data contract ensures:

1. **Observable/hidden separation**: RAY only sees observable features
2. **No future leakage**: Labels unavailable at decision time
3. **Ground truth isolation**: Hidden simulator variables protected
4. **Temporal consistency**: Historical data precedes current opportunity
5. **Reproducibility**: Versioned, immutable datasets
6. **Validation**: Automated checks enforce contract

Violations of this contract invalidate benchmark results.
