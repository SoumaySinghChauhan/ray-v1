# RAY V1 — Constrained Recovery Optimizer v1.0

**Version**: 1.0.0  
**Created**: 2026-08-26  
**Status**: Development Complete  
**Stage**: Prompt 4

---

## Executive Summary

**RAY V1 Constrained Recovery Optimizer** is the economic decision engine that maximizes expected incremental recovery while respecting merchant constraints.

**Key characteristics**:
- Provider-agnostic architecture (interfaces, not models)
- Capacity-constrained optimization (max N actions per day)
- Incremental EV calculation (payment_link_net_EV - do_nothing_EV)
- Deterministic tie-breaking for reproducibility
- Development fixtures for testing (NOT production models)

**Status**: Implementation complete with 14 comprehensive tests passing.

---

## Architecture

### Core Components

```
optimizer/
├── interfaces.py          # Abstract provider interfaces
├── dev_providers.py       # Development fixtures
└── core.py                # Optimizer implementation
```

### Dependency Injection Pattern

```python
# Optimizer depends on interfaces, NOT implementations
optimizer = ConstrainedRecoveryOptimizer(
    prediction_provider=RecoveryProbabilityProvider,  # Interface
    eligibility_provider=ActionEligibilityProvider,   # Interface
    assumed_organic_recovery_rate=0.04,
    intervention_cost=0.0,
    friction_cost=5.0,
    risk_penalty=0.0,
)
```

**Benefits**:
- Optimizer tests without requiring frozen ML models
- Production models swap in later via same interface
- Clear separation: prediction, eligibility, optimization

---

## Interfaces

### RecoveryProbabilityProvider

**Purpose**: Predict probability of recovery if payment link is created

**Method**:
```python
def predict_payment_link_probability(
    self, opportunity: dict[str, Any]
) -> float:
    """Returns probability in [0.0, 1.0]"""
```

**Inputs**: Observable opportunity features only
- failure_class
- amount
- historical_recovery_rate
- historical_success_rate
- avg_payment_amount

**Output**: Float in [0.0, 1.0]

**Error handling**: Invalid predictions (NaN, negative, >1.0) are caught by optimizer

### ActionEligibilityProvider

**Purpose**: Determine if action is eligible for opportunity

**Method**:
```python
def check_eligibility(
    self, opportunity: dict[str, Any], action: str
) -> ActionEligibility:
    """Returns ELIGIBLE or INELIGIBLE"""
```

**Actions**:
- `create_payment_link`: Check policy constraints
- `do_nothing`: Always eligible

**Output**: ActionEligibility enum (ELIGIBLE, INELIGIBLE)

---

## Economic Model

### Incremental EV Calculation

**Goal**: Select opportunities where payment link EV exceeds do-nothing EV

**Formula**:
```
payment_link_gross_EV = payment_link_probability × amount
payment_link_net_EV = payment_link_gross_EV - intervention_cost - friction_cost - risk_penalty

do_nothing_EV = assumed_organic_recovery_rate × amount

incremental_EV = payment_link_net_EV - do_nothing_EV
```

**Decision rule**:
- `incremental_EV > 0` → Candidate for payment link
- `incremental_EV ≤ 0` → Do nothing (organic recovery better)

### Cost Components

| Component | Default | Purpose |
|-----------|---------|---------|
| intervention_cost | ₹0.0 | Direct cost per payment link creation |
| friction_cost | ₹5.0 | Customer friction/goodwill penalty |
| risk_penalty | ₹0.0 | Risk of customer churn |
| assumed_organic_recovery_rate | 0.04 | Business assumption for do_nothing baseline |

**Notes**:
- friction_cost models customer fatigue from repeated contacts
- assumed_organic_recovery_rate is a business assumption (4% organic recovery)
- All costs are per-opportunity, not per-merchant

---

## Optimization Algorithm

### High-Level Flow

```
1. Calculate economic values for all opportunities
2. Filter to eligible positive-EV opportunities
3. Sort by incremental_EV descending (with deterministic tie-breaking)
4. Allocate capacity: select top N
5. Mark capacity-exceeded as skipped
6. Return OptimizationPlan
```

### Deterministic Tie-Breaking

**Purpose**: Reproducible results for same inputs

**Tie-breaking order** (when incremental_EV is equal):
1. Higher `amount` (larger recoverable value)
2. Higher `payment_link_probability`
3. Earlier `occurred_at` timestamp
4. Ascending `opportunity_id` (final deterministic tie-break)

**Example**:
```python
sort_key = (
    incremental_ev,  # Primary: highest EV first
    amount,          # Secondary: larger amounts first
    probability,     # Tertiary: higher probability first
    occurred_at,     # Quaternary: earlier timestamp first
    opportunity_id,  # Final: ascending ID
)
```

### Capacity Constraints

**Constraint**: Maximum N actions per day

**Behavior**:
- Capacity resets each simulated day
- Positive-EV opportunities beyond capacity are marked `CAPACITY_EXCEEDED`
- Negative-EV opportunities are marked `NEGATIVE_INCREMENTAL_VALUE` (not counted against capacity)

**Example**:
- 20 positive-EV opportunities, capacity=10
- Top 10 selected (highest incremental_EV)
- Remaining 10 skipped (CAPACITY_EXCEEDED)

---

## Skip Reasons

**Constrained vocabulary** for why opportunities were not selected:

| SkipReason | Meaning |
|------------|---------|
| NEGATIVE_INCREMENTAL_VALUE | payment_link_net_EV ≤ do_nothing_EV |
| CAPACITY_EXCEEDED | Positive EV but beyond daily capacity limit |
| INELIGIBLE | Policy constraints prohibit action |
| INVALID_PREDICTION | Prediction returned NaN, negative, or >1.0 |
| EXPIRED_OPPORTUNITY | Opportunity past cutoff time |
| DUPLICATE_OPPORTUNITY | Already processed |

---

## Development Fixtures

**Location**: `optimizer/dev_providers.py`

**Purpose**: Enable optimizer testing without frozen ML models

**CRITICAL WARNING**: These are DEVELOPMENT FIXTURES ONLY. Do NOT use for production or final benchmarks.

### DevelopmentRecoveryProbabilityProvider

**Formula**:
```python
# Base from failure class
if failure_class == "soft_decline": base = 0.45
elif failure_class == "hard_decline": base = 0.15
else: base = 0.20

# Adjust by customer history
recovery_adjustment = historical_recovery_rate * 0.3
success_adjustment = historical_success_rate * 0.2

# Adjust by payment value relative to average
if amount > 1.5 * avg_amount: value_adjustment = 0.05
elif amount < 0.5 * avg_amount: value_adjustment = -0.05
else: value_adjustment = 0.0

final_prob = base + recovery_adjustment + success_adjustment + value_adjustment
return bounded(final_prob, 0.0, 1.0)
```

**Characteristics**:
- Deterministic (same inputs → same output)
- Uses ONLY observable features (no hidden ground truth)
- Reasonable predictions (soft_decline: 0.45-0.76, hard_decline: 0.15-0.50)

### DevelopmentEligibilityProvider

**Behavior**: All opportunities ELIGIBLE (for testing)

**Note**: Production policy engine (Prompt 5) will implement real constraints.

---

## Output

### OptimizationPlan

**Structure**:
```python
@dataclass
class OptimizationPlan:
    run_id: str
    merchant_id: str
    simulated_day: int
    created_at: str
    
    daily_capacity: int
    selected_count: int
    
    expected_gross_recovery: float
    expected_net_recovery: float
    expected_incremental_recovery: float
    
    selected_actions: list[OpportunityDecision]
    skipped_actions: list[OpportunityDecision]
```

**Expected value calculations**:
- `expected_gross_recovery`: Sum of payment_link_EV + friction_cost + risk_penalty (for selected)
- `expected_net_recovery`: Sum of payment_link_EV (after costs, for selected)
- `expected_incremental_recovery`: Sum of incremental_EV (for selected)

### OpportunityDecision

**Structure**:
```python
@dataclass
class OpportunityDecision:
    opportunity_id: str
    selected_action: str  # create_payment_link or do_nothing
    
    payment_link_probability: float
    assumed_organic_probability: float
    
    payment_link_ev: float
    do_nothing_ev: float
    incremental_ev: float
    
    eligibility: str
    selection_rank: int | None  # 1, 2, 3... for selected; None for skipped
    skip_reason: str | None
```

---

## Tests

**Location**: `tests/unit/test_optimizer.py`

**Coverage**: 14 comprehensive tests (all passing)

### Test Categories

1. **Capacity Constraints** (3 tests)
   - Plenty of capacity: N < capacity
   - Capacity constrained: N > capacity
   - Capacity reset across days

2. **Economic Calculations** (3 tests)
   - Negative incremental value (friction cost dominates)
   - Exact economic calculation (verify formula)
   - Mixed opportunities (positive + negative EV)

3. **Eligibility Handling** (1 test)
   - Ineligible opportunity (policy constraint)

4. **Invalid Predictions** (3 tests)
   - NaN probability
   - Negative probability
   - Probability above 1.0

5. **Tie-Breaking** (2 tests)
   - Tie-breaking by amount
   - Deterministic output (same inputs → same results)

6. **Ranking Behavior** (2 tests)
   - Selection ranks assigned correctly
   - Highest EV selected first

### Example Test

```python
def test_capacity_constrained(optimizer):
    """More opportunities than capacity."""
    opportunities = [
        create_opportunity(f"opp_{i:03d}", 10000.0, "soft_decline")
        for i in range(20)
    ]
    
    plan = optimizer.optimize_daily_opportunities(
        opportunities=opportunities,
        merchant_id="test_merchant",
        simulated_day=1,
        max_actions_per_day=10,
    )
    
    assert plan.selected_count == 10  # Exactly capacity
    assert len(plan.selected_actions) == 10
    
    capacity_exceeded = [
        d for d in plan.skipped_actions
        if d.skip_reason == SkipReason.CAPACITY_EXCEEDED.value
    ]
    assert len(capacity_exceeded) == 10  # 20 - 10 = 10 exceeded
```

---

## Usage

### Basic Usage

```python
from optimizer.core import ConstrainedRecoveryOptimizer
from optimizer.dev_providers import (
    DevelopmentRecoveryProbabilityProvider,
    DevelopmentEligibilityProvider,
)

# Create optimizer with development fixtures
prediction_provider = DevelopmentRecoveryProbabilityProvider()
eligibility_provider = DevelopmentEligibilityProvider()

optimizer = ConstrainedRecoveryOptimizer(
    prediction_provider=prediction_provider,
    eligibility_provider=eligibility_provider,
    assumed_organic_recovery_rate=0.04,
    intervention_cost=0.0,
    friction_cost=5.0,
    risk_penalty=0.0,
)

# Optimize daily opportunities
opportunities = [
    {
        "opportunity_id": "opp_001",
        "amount": 10000.0,
        "failure_class": "soft_decline",
        "historical_recovery_rate": 0.3,
        "historical_success_rate": 0.6,
        "avg_payment_amount": 10000.0,
        "created_at": "2026-01-01T00:00:00Z",
    },
    # ... more opportunities
]

plan = optimizer.optimize_daily_opportunities(
    opportunities=opportunities,
    merchant_id="merchant_001",
    simulated_day=1,
    max_actions_per_day=10,
)

# Inspect results
print(f"Selected: {plan.selected_count} / {plan.daily_capacity}")
print(f"Expected incremental recovery: ₹{plan.expected_incremental_recovery:.2f}")

for decision in plan.selected_actions:
    print(f"{decision.opportunity_id}: ₹{decision.incremental_ev:.2f}")
```

### Production Usage (Future)

```python
# Production model providers (Prompt 3)
from ml.model_b.predictor import ModelBPredictor  # Future
from policy.engine import PolicyEngine            # Prompt 5

# Create optimizer with production providers
prediction_provider = ModelBPredictor.load("models/model_b_v1.0.0.pkl")
eligibility_provider = PolicyEngine(policy_rules)

optimizer = ConstrainedRecoveryOptimizer(
    prediction_provider=prediction_provider,
    eligibility_provider=eligibility_provider,
    # ... same config
)

# Same API, different providers
plan = optimizer.optimize_daily_opportunities(...)
```

---

## Design Decisions

### Why Interfaces?

**Problem**: Optimizer needs probabilities, but final ML model not frozen yet

**Solution**: Define abstract interfaces, inject providers

**Benefits**:
1. **Testing**: Use development fixtures without ML models
2. **Decoupling**: Optimizer doesn't depend on ML implementation details
3. **Flexibility**: Swap providers (dev fixtures, Model A, Model B, ensemble)
4. **Clarity**: Clean separation of concerns

### Why Incremental EV?

**Alternative**: Select by absolute payment_link_EV

**Problem**: Ignores organic recovery (some customers pay anyway)

**Solution**: Compare payment_link_EV vs do_nothing_EV

**Benefits**:
1. **Correct baseline**: Measures incremental value of intervention
2. **Avoids waste**: Don't contact customers who will pay anyway
3. **Friction accounting**: Properly penalizes unnecessary contacts

### Why Deterministic Tie-Breaking?

**Alternative**: Random tie-breaking

**Problem**: Same inputs produce different results (non-reproducible)

**Solution**: Multi-level deterministic sort key

**Benefits**:
1. **Reproducibility**: Critical for simulation and debugging
2. **Fairness**: Consistent treatment of equal-EV opportunities
3. **Testability**: Can assert exact expected selections

### Why Capacity Constraints?

**Alternative**: Select all positive-EV opportunities

**Problem**: Real merchants have contact limits (rate limits, customer fatigue)

**Solution**: Optimize within constraints, rank by incremental EV

**Benefits**:
1. **Realistic**: Models real operational constraints
2. **Prioritization**: Forces selection of highest-value opportunities
3. **Risk management**: Limits blast radius of poor predictions

---

## Limitations

### Development Fixtures

**CRITICAL**: Development fixtures are NOT production models

**Limitations**:
- Simple deterministic formula (not ML)
- No calibration to real data
- Not trained on diagnosis features
- Will be REPLACED by Model B (Prompt 3)

**Purpose**: Enable optimizer testing only

**Do NOT**:
- Use in final benchmarks
- Report as "Model B performance"
- Compare to baseline using dev fixtures
- Deploy to production

### Economic Assumptions

**assumed_organic_recovery_rate = 0.04** is a business assumption

**Sensitivity**:
- Higher organic rate → fewer opportunities selected (narrower margin)
- Lower organic rate → more opportunities selected (wider margin)

**Future work**: Calibrate organic rate from real data

### Eligibility Provider

**Current**: Development fixture returns ELIGIBLE for all opportunities

**Production**: Policy engine (Prompt 5) will implement:
- Do-not-contact lists
- Contact frequency caps
- Amount limits
- Temporal constraints
- Merchant-specific rules

---

## Integration Points

### From Prompt 3 (ML Models)

**Future**: Replace DevelopmentRecoveryProbabilityProvider with Model B

**Interface contract**:
```python
class ModelBPredictor(RecoveryProbabilityProvider):
    def predict_payment_link_probability(
        self, opportunity: dict[str, Any]
    ) -> float:
        # Model B inference
        features = extract_features(opportunity)
        probability = self.model.predict_proba(features)[0, 1]
        return probability
```

**No changes required** in optimizer (depends on interface)

### To Prompt 5 (Policy Engine)

**Optimizer provides**: Ranked opportunities with economic values

**Policy engine provides**: Eligibility constraints via ActionEligibilityProvider

**Integration**:
```python
from policy.engine import ProductionPolicyEngine

eligibility_provider = ProductionPolicyEngine(
    do_not_contact_list=[...],
    contact_frequency_rules={...},
    amount_limits={...},
)

optimizer = ConstrainedRecoveryOptimizer(
    prediction_provider=model_b_predictor,
    eligibility_provider=eligibility_provider,  # Policy engine
    # ...
)
```

---

## Next Steps

### Immediate (Prompt 4 Complete)

✅ Optimizer implementation complete  
✅ 14 comprehensive tests passing  
✅ Development fixtures working  
✅ Documentation written

### Prompt 5 (Policy Engine)

**Implement**: ActionEligibilityProvider for production

**Features**:
- Do-not-contact list enforcement
- Contact frequency caps
- Amount-based constraints
- Temporal rules (time of day, day of week)
- Merchant-specific policies

**Interface**: Already defined, just implement logic

### Prompt 3 (ML Models - Future)

**Implement**: RecoveryProbabilityProvider for Model B

**Features**:
- Train on diagnosis + observable features
- Calibrate probabilities
- Handle missing values
- Provide prediction confidence

**Interface**: Already defined, just implement inference

### Final Integration

**Steps**:
1. Freeze Model B (Prompt 3)
2. Freeze Policy Engine (Prompt 5)
3. Replace dev fixtures with production providers
4. Run full simulation (Stage D)
5. Generate final benchmark results

---

## Files

### Core Implementation

- `optimizer/interfaces.py` (67 lines)
- `optimizer/dev_providers.py` (146 lines)
- `optimizer/core.py` (335 lines)

### Tests

- `tests/unit/test_optimizer.py` (502 lines, 14 tests)

### Documentation

- `docs/optimizer-v1.0.md` (this file)

---

## Appendix: Skip Reason Decision Tree

```
Opportunity
  │
  ├─ Prediction invalid (NaN, negative, >1.0)?
  │   └─ YES → INVALID_PREDICTION
  │
  ├─ Action ineligible (policy constraint)?
  │   └─ YES → INELIGIBLE
  │
  ├─ Incremental EV ≤ 0?
  │   └─ YES → NEGATIVE_INCREMENTAL_VALUE
  │
  ├─ Within capacity (rank ≤ N)?
  │   ├─ YES → SELECTED (create_payment_link)
  │   └─ NO → CAPACITY_EXCEEDED
```

---

## Appendix: Economic Example

**Scenario**: Soft decline, ₹10,000 amount

**Inputs**:
- failure_class: soft_decline
- amount: ₹10,000
- historical_recovery_rate: 0.5
- historical_success_rate: 0.8

**Development fixture prediction**:
- Base (soft_decline): 0.45
- Recovery adjustment: 0.5 × 0.3 = 0.15
- Success adjustment: 0.8 × 0.2 = 0.16
- Value adjustment: 0.0 (amount = avg)
- **payment_link_probability = 0.76**

**Economic values**:
- payment_link_gross_EV = 0.76 × 10,000 = ₹7,600
- payment_link_net_EV = 7,600 - 0 - 5 - 0 = ₹7,595
- do_nothing_EV = 0.04 × 10,000 = ₹400
- **incremental_EV = 7,595 - 400 = ₹7,195**

**Decision**: CREATE_PAYMENT_LINK (positive incremental EV)

---

**Documentation Version**: 1.0.0  
**Last Updated**: 2026-08-26  
**Status**: Complete
