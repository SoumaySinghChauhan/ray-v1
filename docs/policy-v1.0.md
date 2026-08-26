# RAY V1 — Deterministic Policy Engine v1.0

**Version**: 1.0.0  
**Created**: 2026-08-26  
**Status**: Complete  
**Stage**: Prompt 5

---

## Executive Summary

**RAY V1 Deterministic Policy Engine** is the authorization layer that sits AFTER optimization and BEFORE execution. It answers: **"Is this action permitted?"**

**Key characteristics**:
- Deterministic (same input → same output)
- No re-optimization
- No LLM calls
- No ML predictions
- Pure business logic
- Observable features only

**Status**: Implementation complete with 20 comprehensive tests passing (116 total tests).

---

## Core Principle

The architecture is:

```
Opportunity
    ↓
Prediction (ML Model)
    ↓
Optimizer (Economic Decision)
    ↓
OptimizationPlan
    ↓
POLICY ENGINE (Authorization)
    ↓
ALLOW / BLOCK
    ↓
Execution
```

**The optimizer answers**: "What is economically preferable?"

**The policy engine answers**: "Is this action permitted?"

---

## Authority Boundary

### What Policy Engine DOES

✅ **Authorizes** whether an optimizer-selected action is permitted  
✅ **Enforces** merchant policy constraints  
✅ **Checks** do-not-contact lists  
✅ **Tracks** customer contact frequency  
✅ **Validates** opportunity state  
✅ **Prevents** duplicate actions (idempotency)  
✅ **Enforces** autonomous amount limits  
✅ **Verifies** capacity constraints  

### What Policy Engine DOES NOT DO

❌ **Calculate** economic value  
❌ **Select** a better action  
❌ **Override** optimizer ranking  
❌ **Call** LLMs  
❌ **Call** Razorpay  
❌ **Modify** ML predictions  
❌ **Access** simulator ground truth  
❌ **Create** payment links  
❌ **Re-optimize** selections  

**Policy is deterministic authorization only.**

---

## V1 Policy Output

**V1 policy output is exactly**:

- **ALLOW**: Action is permitted
- **BLOCK**: Action is not permitted

**V1 does NOT implement**:
- REQUIRE_APPROVAL
- ESCALATE
- CONDITIONAL_ALLOW

These are reserved for future versions.

---

## V1 Policy Rules

**Policy evaluates exactly 7 rules** (in order):

| # | Rule ID | Purpose | Block Reason |
|---|---------|---------|--------------|
| 1 | VALID_ACTION_TYPE | Only create_payment_link is executable | INVALID_ACTION |
| 2 | OPPORTUNITY_ACTIONABLE | Opportunity must not be recovered/closed/expired | OPPORTUNITY_NOT_ACTIONABLE |
| 3 | DO_NOT_CONTACT_CHECK | Customer must not be on DNC list | DO_NOT_CONTACT |
| 4 | DUPLICATE_ACTION_CHECK | Action must not be already executed | DUPLICATE_ACTION |
| 5 | AUTONOMOUS_AMOUNT_LIMIT_CHECK | Amount must be ≤ ₹25,000 | AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED |
| 6 | MAX_CONTACTS_CHECK | Customer contact count < max_per_day | MAX_CONTACTS_EXCEEDED |
| 7 | DAILY_CAPACITY_CHECK | Total actions ≤ max_actions_per_day | DAILY_CAPACITY_EXCEEDED |

**Rule evaluation order is deterministic and documented.**

**First failing rule** becomes the primary block reason.

---

## Rule Details

### Rule 1: Valid Action Type

**Purpose**: Only `create_payment_link` requires execution authorization.

**Logic**:
```python
if action == "create_payment_link":
    PASS
else:
    BLOCK (INVALID_ACTION)
```

**Note**: `do_nothing` doesn't need policy authorization (it's a non-action).

---

### Rule 2: Opportunity Actionable

**Purpose**: Opportunity must still be valid for intervention.

**Non-actionable states**:
- `recovered` (already paid)
- `closed` (manually closed)
- `expired` (past cutoff)
- `cancelled` (order cancelled)
- `blocked` (manually blocked)
- `safe_halt` (safety override)

**Logic**:
```python
if opportunity_state in non_actionable_states:
    BLOCK (OPPORTUNITY_NOT_ACTIONABLE)
else:
    PASS
```

**Actionable states**:
- `SCORABLE` (planning phase)
- `PLANNING` (optimizer running)
- `ACTION_SELECTED` (optimizer complete)
- `POLICY_CHECK` (policy evaluating)
- `None` (no state recorded yet)

---

### Rule 3: Do-Not-Contact

**Purpose**: Respect customer communication preferences.

**Logic**:
```python
if customer_id in merchant_policy.do_not_contact_list:
    BLOCK (DO_NOT_CONTACT)
else:
    PASS
```

**Priority**: This rule **overrides all economic decisions**.

**Example**:
- Even if incremental_EV = ₹10,000
- If customer on DNC list
- Action is BLOCKED

**LLM cannot override** this rule.  
**Optimizer cannot override** this rule.

---

### Rule 4: Duplicate Action (Idempotency)

**Purpose**: Prevent duplicate execution of same action.

**Action identity**:
```
(merchant_id, opportunity_id, action_type)
```

**Logic**:
```python
action_key = (merchant_id, opportunity_id, action_type)
if action_key in execution_state.executed_actions:
    BLOCK (DUPLICATE_ACTION)
else:
    PASS
```

**Example**:
- Payment link already created for opportunity
- Second attempt: BLOCKED

**Note**: If earlier execution failed, retry semantics are handled by execution layer (not policy).

---

### Rule 5: Autonomous Amount Limit

**Purpose**: Limit autonomous actions to safe amounts.

**V1 Configuration**: `autonomous_amount_limit = ₹25,000`

**Logic**:
```python
if amount > autonomous_amount_limit:
    BLOCK (AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED)
else:
    PASS
```

**Examples**:
- ₹24,999: ALLOW
- ₹25,000: ALLOW
- ₹25,001: BLOCK

**V1 does NOT implement approval workflow** for amounts > limit.

---

### Rule 6: Max Contacts Per Customer

**Purpose**: Prevent customer fatigue from repeated contacts.

**V1 Configuration**: `max_contacts_per_customer_per_day = 1`

**Logic**:
```python
contact_key = (merchant_id, customer_id, simulated_day)
current_contacts = execution_state.customer_contact_counts[contact_key]

if current_contacts >= max_contacts_per_customer_per_day:
    BLOCK (MAX_CONTACTS_EXCEEDED)
else:
    PASS
```

**Example**:
- Customer contacted once today: 1st action ALLOWED
- Customer contacted once today: 2nd action BLOCKED

**Contact definition**: Creating/sending a Payment Link counts as one contact.

---

### Rule 7: Daily Capacity

**Purpose**: Defensive verification of optimizer capacity allocation.

**V1 Configuration**: `max_actions_per_day = 10`

**Logic**:
```python
if actions_allowed_count >= max_actions_per_day:
    BLOCK (DAILY_CAPACITY_EXCEEDED)
else:
    PASS
```

**Note**: Optimizer already allocates within capacity. This is a **defensive safety check**.

**Behavior**:
- If optimizer produces 10 selected actions → all may pass (if eligible)
- If optimizer produces 15 selected actions (malformed) → only first 10 eligible allowed

---

## Policy Configuration

**V1 defaults** (from centralized config):

```python
max_actions_per_day = 10
max_contacts_per_customer_per_day = 1
autonomous_amount_limit = ₹25,000
policy_version = "1.0.0"
```

**Do-not-contact list**: Loaded from customer state (merchant-specific).

**Configuration is centralized** in `config/v1_config.py`.

**Configuration is versioned**: Changes require version bump.

---

## Policy Decision Structure

### PolicyDecision

```python
@dataclass
class PolicyDecision:
    decision: str                    # "ALLOW" or "BLOCK"
    opportunity_id: str
    action_type: str
    policy_version: str              # "1.0.0"
    evaluated_at: str                # ISO 8601 timestamp
    primary_reason: str | None       # BlockReason if BLOCK, None if ALLOW
    all_rule_results: list[RuleResult]
```

**Example (ALLOW)**:
```json
{
  "decision": "ALLOW",
  "opportunity_id": "opp_001",
  "action_type": "create_payment_link",
  "policy_version": "1.0.0",
  "evaluated_at": "2026-08-26T10:00:00Z",
  "primary_reason": null,
  "all_rule_results": [
    {"rule_id": "VALID_ACTION_TYPE", "passed": true, ...},
    {"rule_id": "OPPORTUNITY_ACTIONABLE", "passed": true, ...},
    ...
  ]
}
```

**Example (BLOCK)**:
```json
{
  "decision": "BLOCK",
  "opportunity_id": "opp_002",
  "action_type": "create_payment_link",
  "policy_version": "1.0.0",
  "evaluated_at": "2026-08-26T10:00:00Z",
  "primary_reason": "DO_NOT_CONTACT",
  "all_rule_results": [
    {"rule_id": "VALID_ACTION_TYPE", "passed": true, ...},
    {"rule_id": "OPPORTUNITY_ACTIONABLE", "passed": true, ...},
    {"rule_id": "DO_NOT_CONTACT_CHECK", "passed": false, "reason": "Customer on do-not-contact list", ...}
  ]
}
```

---

## Rule Result Structure

### RuleResult

```python
@dataclass
class RuleResult:
    rule_id: str                     # Rule identifier
    passed: bool                     # True if rule passed
    reason: str | None               # Explanation if failed
    observed_value: Any | None       # Actual value observed
    configured_value: Any | None     # Expected/configured value
```

**Example (passed)**:
```json
{
  "rule_id": "AUTONOMOUS_AMOUNT_LIMIT_CHECK",
  "passed": true,
  "reason": null,
  "observed_value": 15000.0,
  "configured_value": 25000.0
}
```

**Example (failed)**:
```json
{
  "rule_id": "AUTONOMOUS_AMOUNT_LIMIT_CHECK",
  "passed": false,
  "reason": "Amount ₹30000.00 exceeds autonomous limit ₹25000.00",
  "observed_value": 30000.0,
  "configured_value": 25000.0
}
```

---

## Policy Evaluation API

### Single Action Evaluation

```python
def evaluate_action(
    opportunity: dict[str, Any],
    action: str,
    merchant_policy: MerchantPolicy,
    execution_state: ExecutionState,
    simulated_day: int,
) -> PolicyDecision
```

**Purpose**: Evaluate whether a single action is permitted.

**Returns**: PolicyDecision with ALLOW or BLOCK.

---

### Plan-Level Evaluation

```python
def evaluate_optimization_plan(
    optimization_plan: OptimizationPlan,
    merchant_policy: MerchantPolicy,
    execution_state: ExecutionState,
    opportunities: list[dict[str, Any]],
) -> PolicyEvaluationResult
```

**Purpose**: Evaluate an entire optimization plan.

**Returns**: PolicyEvaluationResult with:
- `allowed_actions`: list[PolicyDecision]
- `blocked_actions`: list[PolicyDecision]
- `block_reasons`: dict[str, int] (reason → count)
- Summary statistics

---

## Policy Evaluation Result

### PolicyEvaluationResult

```python
@dataclass
class PolicyEvaluationResult:
    plan_id: str
    policy_version: str
    evaluated_at: str
    
    allowed_actions: list[PolicyDecision]
    blocked_actions: list[PolicyDecision]
    
    total_evaluated: int
    total_allowed: int
    total_blocked: int
    
    block_reasons: dict[str, int]
```

**Example**:
```json
{
  "plan_id": "run_12345",
  "policy_version": "1.0.0",
  "evaluated_at": "2026-08-26T10:00:00Z",
  "total_evaluated": 10,
  "total_allowed": 7,
  "total_blocked": 3,
  "block_reasons": {
    "DO_NOT_CONTACT": 2,
    "AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED": 1
  }
}
```

---

## Deterministic Behavior

**Key principle**: Same input → same output (except timestamp).

**Deterministic inputs**:
- Opportunity data
- Merchant policy configuration
- Execution state
- Simulated day

**Deterministic outputs**:
- Decision (ALLOW or BLOCK)
- Primary reason
- Rule results

**NOT deterministic**:
- `evaluated_at` timestamp (always current time)

**No randomness**:
- No random sampling
- No probabilistic checks
- No LLM calls
- No external API calls

---

## Idempotency Behavior

**Purpose**: Prevent duplicate execution of same action.

**Idempotency key**:
```
(merchant_id, opportunity_id, action_type)
```

**Logic**:
1. Before ALLOW: Check if action already executed
2. If already executed: BLOCK (DUPLICATE_ACTION)
3. If not executed: Continue evaluation

**Example scenario**:
- Day 1: Action executed successfully → recorded in execution_state
- Day 2: Optimizer selects same action again → policy BLOCKS (duplicate)

**Retry handling**:
- If earlier execution failed (API error, timeout): Retry semantics handled by execution layer
- Policy checks only successful executions

---

## Capacity Behavior

**Two-level capacity enforcement**:

1. **Optimizer** (primary): Allocates capacity, selects top N opportunities
2. **Policy** (defensive): Verifies capacity not exceeded

**Normal case**:
- Optimizer selects 10 actions (capacity = 10)
- Policy verifies: 10 ≤ 10 → all may pass (if eligible)

**Defensive case** (optimizer bug):
- Optimizer selects 15 actions (capacity = 10)
- Policy blocks: Only first 10 eligible allowed, remaining 5 BLOCKED

**Capacity resets**: Each simulated day (independent).

---

## Contact Behavior

**Max contacts per customer per day**: 1 (V1)

**Tracking**:
- Key: `(merchant_id, customer_id, simulated_day)`
- Value: contact count

**Logic**:
```
if customer_contact_count >= 1:
    BLOCK (MAX_CONTACTS_EXCEEDED)
```

**Within-plan enforcement**:
- If multiple actions for same customer in one plan
- First eligible action: ALLOWED (contact count = 0 → 1)
- Second eligible action: BLOCKED (contact count = 1 → exceeds limit)

**Example**:
- Customer has 2 failed payments (2 opportunities)
- Optimizer selects both (malformed plan)
- Policy: ALLOW first, BLOCK second

---

## Security Boundary

**Policy only accesses**:
- ✅ Observable opportunity features
- ✅ Merchant policy configuration
- ✅ Customer do-not-contact flag
- ✅ Execution/idempotency state
- ✅ Optimizer output

**Policy NEVER accesses**:
- ❌ Hidden simulator variables
- ❌ True recovery probabilities
- ❌ Hidden customer traits
- ❌ LLM prompt internals
- ❌ Test-set labels
- ❌ Future outcomes

**Purpose**: Maintain experimental integrity.

---

## Policy Versioning

**V1 policy version**: `"1.0.0"`

**Version recorded on**:
- Every PolicyDecision
- Every PolicyEvaluationResult

**Version changes when**:
- Rules added/removed
- Rule logic modified
- Configuration defaults changed
- Block reasons changed

**Version does NOT change when**:
- Only implementation refactored (same logic)
- Comments/documentation updated
- Tests added

**Historical decisions**: Never mutated retroactively.

---

## Block Reasons

**Constrained vocabulary**:

| Block Reason | Rule | Description |
|--------------|------|-------------|
| INVALID_ACTION | Rule 1 | Action type not executable |
| OPPORTUNITY_NOT_ACTIONABLE | Rule 2 | Opportunity recovered/closed/expired |
| DO_NOT_CONTACT | Rule 3 | Customer on DNC list |
| DUPLICATE_ACTION | Rule 4 | Action already executed |
| AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED | Rule 5 | Amount > ₹25,000 |
| MAX_CONTACTS_EXCEEDED | Rule 6 | Customer already contacted today |
| DAILY_CAPACITY_EXCEEDED | Rule 7 | Daily action capacity exceeded |

**Primary reason**: First failing rule in evaluation order.

---

## Tests

**Location**: `tests/unit/test_policy.py`

**Total**: 20 comprehensive tests (all passing)

### Test Categories

1. **Basic Rules** (7 tests)
   - Valid action (ALLOW)
   - Do-not-contact (BLOCK)
   - Amount limit exceeded (BLOCK)
   - Max contacts exceeded (BLOCK)
   - Opportunity not actionable (BLOCK)
   - Duplicate action (BLOCK)
   - Invalid action (BLOCK)

2. **Capacity Enforcement** (2 tests)
   - Capacity exactly at limit (ALLOW final slot)
   - Capacity exceeded (BLOCK excess)

3. **Contact Tracking** (1 test)
   - Two actions same customer (BLOCK second)

4. **Determinism** (1 test)
   - Same input → same output

5. **Observable Features** (1 test)
   - Policy works without hidden simulator data

6. **Rule Ordering** (2 tests)
   - Invalid action checked first
   - Do-not-contact before amount limit

7. **Adversarial Scenarios** (6 tests)
   - Amount ₹25,001 (just over limit)
   - Amount ₹25,000 (exactly at limit)
   - Malformed opportunity
   - Unknown action string
   - Optimizer exceeds capacity
   - Multiple violations

---

## Usage Examples

### Single Action

```python
from policy.engine import DeterministicPolicyEngine
from policy.types import MerchantPolicy, ExecutionState

# Create policy engine
policy_engine = DeterministicPolicyEngine(policy_version="1.0.0")

# Configure merchant policy
merchant_policy = MerchantPolicy(
    merchant_id="merchant_001",
    max_actions_per_day=10,
    max_contacts_per_customer_per_day=1,
    autonomous_amount_limit=25000.0,
    policy_version="1.0.0",
    do_not_contact_list={"cust_blocked_1", "cust_blocked_2"},
)

# Create execution state
execution_state = ExecutionState.create_empty()

# Evaluate action
opportunity = {
    "opportunity_id": "opp_001",
    "customer_id": "cust_001",
    "amount": 15000.0,
    "failure_class": "soft_decline",
    "created_at": "2026-01-01T00:00:00Z",
}

decision = policy_engine.evaluate_action(
    opportunity=opportunity,
    action="create_payment_link",
    merchant_policy=merchant_policy,
    execution_state=execution_state,
    simulated_day=1,
)

if decision.decision == "ALLOW":
    print(f"Action allowed for {opportunity['opportunity_id']}")
else:
    print(f"Action blocked: {decision.primary_reason}")
```

### Optimization Plan

```python
# Evaluate entire plan
result = policy_engine.evaluate_optimization_plan(
    optimization_plan=optimization_plan,
    merchant_policy=merchant_policy,
    execution_state=execution_state,
    opportunities=opportunities,
)

print(f"Evaluated: {result.total_evaluated}")
print(f"Allowed: {result.total_allowed}")
print(f"Blocked: {result.total_blocked}")

for reason, count in result.block_reasons.items():
    print(f"  - {reason}: {count}")

# Execute allowed actions
for decision in result.allowed_actions:
    execute_payment_link(decision.opportunity_id)
```

---

## Integration Points

### FROM Optimizer (Prompt 4)

**Policy receives**: OptimizationPlan with selected actions

**Interface**:
```python
@dataclass
class OptimizationPlan:
    run_id: str
    merchant_id: str
    simulated_day: int
    selected_actions: list[OpportunityDecision]
    ...
```

**Policy evaluates**: Each selected action for authorization.

---

### TO Execution (Prompt 6 - Future)

**Policy provides**: List of ALLOWED actions

**Execution layer**:
- Creates Payment Links for allowed actions
- Records execution in execution_state
- Updates customer contact counts
- Updates opportunity states
- Handles webhooks

**Integration**:
```python
# Policy evaluation
result = policy_engine.evaluate_optimization_plan(...)

# Execute allowed actions
for decision in result.allowed_actions:
    payment_link = create_razorpay_payment_link(decision.opportunity_id)
    record_execution(decision, payment_link)
```

---

## Known Limitations

### V1 Limitations

**No approval workflow**:
- Amounts > ₹25,000 are simply BLOCKED
- No escalation to human review
- Future: Add REQUIRE_APPROVAL decision type

**No temporal constraints**:
- No time-of-day restrictions
- No day-of-week restrictions
- Future: Add temporal policy rules

**No merchant-specific overrides**:
- Same rules apply to all merchants
- No per-merchant amount limits
- Future: Add merchant-specific policy configuration

**No channel-specific logic**:
- Only Payment Link channel supported
- Future: Add email, SMS, WhatsApp channels

**No risk scoring**:
- No fraud detection
- No customer risk tiers
- Future: Integrate with risk engine

---

## Design Decisions

### Why Deterministic?

**Problem**: Non-deterministic policy makes debugging impossible.

**Solution**: Pure business logic, no randomness, no LLM calls.

**Benefits**:
- Reproducible results
- Testable
- Auditable
- Predictable

---

### Why Rule Ordering?

**Problem**: Multiple violations → which is "primary"?

**Solution**: Deterministic evaluation order, first failure is primary.

**Benefits**:
- Consistent reason assignment
- Predictable for testing
- Clear for debugging

---

### Why Defensive Capacity Check?

**Problem**: What if optimizer has a bug and violates capacity?

**Solution**: Policy independently verifies capacity.

**Benefits**:
- Safety mechanism
- Protects execution layer
- Prevents API rate limit violations

---

### Why Separate from Optimizer?

**Problem**: Mixing economics and authorization makes both complex.

**Solution**: Clear separation of concerns.

**Benefits**:
- Optimizer focuses on economic value
- Policy focuses on authorization
- Each can be tested independently
- Clear responsibility boundary

---

## Next Steps

### Immediate (Prompt 5 Complete)

✅ Policy engine implementation complete  
✅ 20 comprehensive tests passing  
✅ Documentation written  
✅ 116 total tests passing

### Prompt 6 (Next)

**Implement**: Razorpay Payment Link Execution + Webhook Outcome Handling

**Features**:
- Create Payment Links for allowed actions
- Record execution in execution_state
- Handle Razorpay webhooks
- Update opportunity states
- Track actual outcomes
- Compare predictions vs actuals

**Integration**: Consume policy evaluation results, execute allowed actions.

---

## Files

### Core Implementation

- `policy/types.py` (132 lines)
- `policy/engine.py` (509 lines)

### Tests

- `tests/unit/test_policy.py` (679 lines, 20 tests)

### Documentation

- `docs/policy-v1.0.md` (this file)

---

## Appendix: Rule Evaluation Flow

```
evaluate_action(opportunity, action, merchant_policy, execution_state, simulated_day)
  │
  ├─ Rule 1: Valid Action Type?
  │   ├─ FAIL → BLOCK (INVALID_ACTION)
  │   └─ PASS → continue
  │
  ├─ Rule 2: Opportunity Actionable?
  │   ├─ FAIL → BLOCK (OPPORTUNITY_NOT_ACTIONABLE)
  │   └─ PASS → continue
  │
  ├─ Rule 3: Do-Not-Contact?
  │   ├─ FAIL → BLOCK (DO_NOT_CONTACT)
  │   └─ PASS → continue
  │
  ├─ Rule 4: Duplicate Action?
  │   ├─ FAIL → BLOCK (DUPLICATE_ACTION)
  │   └─ PASS → continue
  │
  ├─ Rule 5: Amount ≤ Limit?
  │   ├─ FAIL → BLOCK (AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED)
  │   └─ PASS → continue
  │
  ├─ Rule 6: Contacts < Max?
  │   ├─ FAIL → BLOCK (MAX_CONTACTS_EXCEEDED)
  │   └─ PASS → continue
  │
  └─ All Rules Passed
      └─ ALLOW
```

---

## Appendix: Example Scenarios

### Scenario 1: Valid Action (ALLOW)

**Input**:
- Opportunity: opp_001, customer cust_001, amount ₹15,000
- Action: create_payment_link
- Customer NOT on DNC
- No prior contact today
- No prior execution

**Evaluation**:
1. Valid action type? ✅ PASS
2. Opportunity actionable? ✅ PASS (no state = actionable)
3. Do-not-contact? ✅ PASS (not on list)
4. Duplicate action? ✅ PASS (not executed)
5. Amount ≤ ₹25,000? ✅ PASS (15,000 ≤ 25,000)
6. Contacts < 1? ✅ PASS (0 < 1)
7. Capacity OK? ✅ PASS

**Result**: ALLOW

---

### Scenario 2: Do-Not-Contact (BLOCK)

**Input**:
- Opportunity: opp_002, customer cust_dnc, amount ₹10,000
- Action: create_payment_link
- Customer ON DNC list

**Evaluation**:
1. Valid action type? ✅ PASS
2. Opportunity actionable? ✅ PASS
3. Do-not-contact? ❌ FAIL (on list)

**Result**: BLOCK (DO_NOT_CONTACT)

---

### Scenario 3: Amount Exceeds Limit (BLOCK)

**Input**:
- Opportunity: opp_003, customer cust_003, amount ₹30,000
- Action: create_payment_link

**Evaluation**:
1. Valid action type? ✅ PASS
2. Opportunity actionable? ✅ PASS
3. Do-not-contact? ✅ PASS
4. Duplicate action? ✅ PASS
5. Amount ≤ ₹25,000? ❌ FAIL (30,000 > 25,000)

**Result**: BLOCK (AUTONOMOUS_AMOUNT_LIMIT_EXCEEDED)

---

**Documentation Version**: 1.0.0  
**Last Updated**: 2026-08-26  
**Status**: Complete
