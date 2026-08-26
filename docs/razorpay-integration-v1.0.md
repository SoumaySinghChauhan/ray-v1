# RAY V1 — Razorpay Integration v1.0

**Version**: 1.0.0  
**Created**: 2026-08-26  
**Status**: Complete (TEST MODE ONLY)

---

## Executive Summary

**Razorpay Payment Link integration** implements execution and outcome tracking for RAY V1.

**Key features**:
- Payment Link creation via Razorpay API (TEST MODE ONLY)
- Webhook handling with signature verification
- Idempotency for execution and webhooks
- Recovery outcome tracking
- Stale event protection
- Comprehensive security measures

**Status**: All 142 tests passing (116 existing + 26 new).

---

## Security Constraints

### TEST MODE ONLY

**RAY V1 ONLY SUPPORTS TEST MODE.**

**Requirements**:
- `RAZORPAY_MODE=test` (enforced)
- Test API keys only
- Live mode explicitly disabled

**Enforcement**:
- Startup validation rejects `live` mode
- RazorpayPaymentLinkExecutor constructor rejects `live` mode
- Environment loader validates `test` mode

### No Live Mode in V1

**V1 explicitly does NOT support**:
- Live API keys
- Production Payment Link creation
- Real customer charges
- Live merchant operations

---

## Configuration

### Required Environment Variables

```bash
# Razorpay (TEST MODE)
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxx
```

**Never**:
- Hard-code credentials
- Commit credentials to repository
- Log credentials
- Include credentials in error messages

---

## Architecture

```
PolicyDecision (ALLOW)
    ↓
ExecutionService
    ↓
PaymentLinkExecutor (Razorpay or Mock)
    ↓
Razorpay API (TEST MODE)
    ↓
ExecutionAttempt persisted
    ↓
Webhook received
    ↓
Signature verified
    ↓
Event processed
    ↓
RecoveryOutcome created
    ↓
Opportunity state updated
```

---

## Payment Link Execution

### Execution Flow

1. **Policy authorization**: PolicyDecision must be ALLOW
2. **Idempotency check**: Check if already executed
3. **Create Payment Link**: Call Razorpay API
4. **Persist execution**: Record ExecutionAttempt
5. **Update state**: Opportunity → ACTION_EXECUTED
6. **Increment contact count**: Customer contact count++

### Idempotency

**Idempotency key**: `SHA256(merchant_id:opportunity_id:action_type:policy_version)`

**Behavior**:
- If already executed successfully → return existing result
- If previous attempt failed → follow retry semantics
- Execution recorded BEFORE Razorpay call to detect duplicates

### Execution States

| State | Meaning |
|-------|---------|
| PENDING | Authorized but not yet sent |
| SUBMITTED | Request sent to Razorpay |
| SUCCEEDED | Payment Link created successfully |
| FAILED | Definite failure from Razorpay |
| UNKNOWN | Outcome cannot be determined (DO NOT RETRY) |
| CANCELLED | Intentionally stopped |

**UNKNOWN state**:
- Used when result is ambiguous (timeout, network error)
- DO NOT automatically retry (risk of duplicate creation)
- Reconcile using reference_id fetch

---

## Payment Link Request

### Standard Payment Link

```python
{
    "amount": 1000000,  # paise (₹10,000)
    "currency": "INR",
    "reference_id": "RAY-opp_001-a1b2c3d4",
    "description": "RAY Payment Recovery - opp_001",
    "expire_by": 1724793600,  # Unix timestamp
    "notes": {
        "ray_opportunity_id": "opp_001",
        "ray_execution_id": "exec_uuid",
        "ray_policy_version": "1.0.0"
    },
    "customer": {
        "contact": "+919876543210",
        "email": "customer@example.com",
        "name": "Customer Name"
    }
}
```

### Reference ID

**Format**: `RAY-{opportunity_id}-{hash}`

**Properties**:
- Deterministic (same opportunity → same reference_id)
- Unique per opportunity
- Used for execution resolution
- Within Razorpay constraints

### Expiry

**Default**: 24 hours from creation

**Configurable**: `expiry_hours` parameter

---

## Webhook Handling

### Supported Events

| Event | Outcome | State |
|-------|---------|-------|
| payment_link.paid | RECOVERED | RECOVERED |
| payment_link.partially_paid | PARTIALLY_RECOVERED | PARTIALLY_RECOVERED |
| payment_link.cancelled | CANCELLED | CANCELLED |
| payment_link.expired | EXPIRED | EXPIRED |

### Signature Verification

**Algorithm**: HMAC-SHA256

**Process**:
1. Receive raw request body (bytes)
2. Extract `X-Razorpay-Signature` header
3. Calculate HMAC: `HMAC-SHA256(raw_body, webhook_secret)`
4. Compare signatures (constant-time comparison)
5. Reject if invalid

**Security**:
- Verify BEFORE parsing JSON
- Reject if secret missing
- Log verification failures
- Never log webhook secret

### Webhook Idempotency

**Event identity**: Razorpay `id` field (fallback to `event` field)

**Behavior**:
- Track processed event IDs
- If duplicate → return success (already processed)
- Never process same event twice

### Stale Event Protection

**Problem**: Late webhooks can arrive after terminal states

**Examples**:
- `payment_link.expired` arrives after `payment_link.paid`
- `payment_link.cancelled` arrives after `payment_link.paid`

**Protection**:
- Check current state before updating
- Terminal states (RECOVERED, PARTIALLY_RECOVERED) cannot be downgraded
- Ignore stale events that would downgrade state

---

## Recovery Outcomes

### RecoveryOutcome

```python
@dataclass
class RecoveryOutcome:
    outcome_id: str
    opportunity_id: str
    execution_id: str
    outcome_type: str  # RECOVERED, PARTIALLY_RECOVERED, etc.
    amount_recovered: float
    currency: str
    razorpay_payment_id: str | None
    razorpay_payment_link_id: str
    source_event_id: str
    observed_at: str
    notes: dict | None
```

### Outcome Types

| Type | Meaning |
|------|---------|
| RECOVERED | Full payment received |
| PARTIALLY_RECOVERED | Partial payment received |
| EXPIRED | Payment Link expired without payment |
| CANCELLED | Payment Link cancelled |
| UNKNOWN | Outcome unknown/ambiguous |

---

## Opportunity States

### State Transitions

```
ACTION_SELECTED
    ↓
POLICY_CHECK
    ↓
EXECUTING
    ↓
ACTION_EXECUTED / AWAITING_OUTCOME
    ↓
RECOVERED / PARTIALLY_RECOVERED / EXPIRED / CANCELLED
```

**After execution**: `ACTION_EXECUTED`

**After outcome**: Terminal state (RECOVERED, etc.)

---

## Testing

### Mock Executor

**Purpose**: Test execution without Razorpay API

**Usage**:
```python
executor = MockPaymentLinkExecutor(should_succeed=True)
service = ExecutionService(executor=executor)
```

**Behavior**:
- Deterministic results
- No external API calls
- Tracks created links for verification

### Test Coverage

**Total tests**: 142 (116 existing + 26 new)

**New tests**:
- Execution: 14 tests
- Webhooks: 12 tests

**Categories**:
- Execution success/failure
- Idempotency
- Contact tracking
- State management
- Signature verification
- Event processing
- Stale event protection
- Security constraints

---

## Razorpay Test Mode Limitations

**Test Mode limits**:
- 30 Payment Links per business
- Test data only (no real charges)
- Test webhooks (manual trigger)

**Design considerations**:
- Dedicated test command with confirmation flag
- No bulk execution in tests
- No automatic real API calls

---

## Manual Testing

### Single Payment Link Test

**Command**: `python scripts/test_razorpay_payment_link.py --confirm-test-link`

**Safety**:
- Requires `--confirm-test-link` flag
- Validates TEST MODE
- Creates exactly 1 Payment Link
- Prints safe information only

**Output**:
- Success/failure status
- Razorpay Payment Link ID
- Short URL
- Reference ID

**NOT output**:
- Credentials
- Secrets
- Full responses

---

## Security Practices

### Credentials

**Storage**:
- Environment variables ONLY
- Never in code
- Never in repository
- Never in logs

**Access**:
- Loaded at startup
- Never logged
- Never in error messages
- Never in audit trails

### Webhook Security

**Verification**:
- HMAC-SHA256 signature
- Verify before parsing
- Constant-time comparison
- Reject if invalid

**Secrets**:
- Never log webhook secret
- Never include in responses
- Load from environment only

### Hidden Data

**Never send to Razorpay**:
- Simulator ground truth
- True recovery probabilities
- Hidden customer traits
- Internal ML features
- Test-set labels

**Only send**:
- Observable opportunity data
- Safe metadata (opportunity_id, execution_id)
- Customer contact info

---

## Error Handling

### Razorpay Errors

| Error | State | Retry? |
|-------|-------|--------|
| Validation | FAILED | No |
| Authentication | FAILED | No |
| Duplicate reference | FAILED | No |
| Timeout | UNKNOWN | Reconcile |
| Server error | UNKNOWN | Reconcile |
| Network error | UNKNOWN | Reconcile |

### UNKNOWN State Handling

**Process**:
1. Mark execution UNKNOWN
2. Persist state
3. Attempt reconciliation via reference_id fetch
4. Resolve to SUCCEEDED or FAILED
5. DO NOT auto-retry (financial safety)

---

## Audit Trail

**Every execution records**:
- execution_id
- opportunity_id
- action_type
- policy_version
- Razorpay identifiers
- Timestamps
- State transitions
- Error messages

**Never records**:
- Credentials
- Secrets
- Hidden simulator data

---

## Integration Points

### FROM Policy (Prompt 5)

**Input**: PolicyDecision with ALLOW

**Process**:
1. Verify ALLOW decision
2. Check idempotency
3. Create Payment Link
4. Return ExecutionResult

### TO Evaluation (Future)

**Output**: RecoveryOutcome records

**Use**:
- Compare predictions vs actuals
- Calculate recovered revenue
- Measure incremental value
- Validate ML models

---

## Known Limitations

### V1 Limitations

**No approval workflow**:
- Amounts > ₹25,000 blocked by policy
- No escalation to human review

**No retry logic**:
- Failed executions not automatically retried
- UNKNOWN state requires manual reconciliation

**In-memory storage**:
- Execution records in memory (not database)
- Webhook events in memory
- TODO: Database persistence

**No bulk execution**:
- One-at-a-time execution only
- No parallel Payment Link creation

---

## References

**Razorpay Documentation**:
- Payment Links API: https://razorpay.com/docs/api/payments/payment-links/
- Webhooks: https://razorpay.com/docs/webhooks/payment-links/
- Test Mode: https://razorpay.com/docs/payments/dashboard/account-settings/test-live/

**Internal Documentation**:
- Optimizer v1.0: docs/optimizer-v1.0.md
- Policy v1.0: docs/policy-v1.0.md

---

**Documentation Version**: 1.0.0  
**Last Updated**: 2026-08-26  
**Status**: Complete (TEST MODE ONLY)
