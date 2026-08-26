# RAY V1 - Webhook Configuration Preflight Report

**Date**: 2026-08-26  
**Target Payment Link**: plink_TUHmPcKkJIlbli  
**Purpose**: Webhook implementation status and readiness assessment

---

## Executive Summary

**STATUS**: ⚠️ **WEBHOOK ENDPOINT NOT IMPLEMENTED**

The webhook handler (`WebhookHandler`) exists and is fully tested, but it is **NOT integrated** with the FastAPI application. The FastAPI webhook route returns `501 NOT IMPLEMENTED`.

**Integration required** before webhooks can be tested.

---

## 1. FastAPI Webhook Route/Path

**Route**: `/webhooks/razorpay`

**Location**: `services/api/main.py:99-113`

**Current implementation**:
```python
@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    """
    Razorpay webhook receiver.

    IMPORTANT: Must verify webhook signature before processing.
    Implementation deferred to later prompt.
    """
    # Signature verification would happen here
    # Payload parsing and event handling would follow

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "Webhook processing not yet implemented"}
    )
```

**Status**: ❌ **SCAFFOLDED ONLY** - Returns 501 (Not Implemented)

---

## 2. HTTP Method

**Method**: `POST`

**Decorator**: `@app.post("/webhooks/razorpay")`

**Razorpay requirement**: POST (correct)

---

## 3. Raw Request Body Capture

**Current implementation**: ❌ **NOT CAPTURED**

**FastAPI route uses**: `request: Request`

**Problem**: The route does not currently extract the raw body

**Required implementation**:
```python
raw_body = await request.body()  # bytes
```

**Critical**: Raw body MUST be captured BEFORE parsing JSON for signature verification

**Signature verification requires**:
- Raw body bytes (unchanged)
- X-Razorpay-Signature header
- Webhook secret

**Current gap**: Route does not call `request.body()` or pass to webhook handler

---

## 4. Signature Verification Implementation

**Function**: `verify_webhook_signature()` in `execution/providers.py:343-370`

**Algorithm**: HMAC-SHA256

**Implementation**:
```python
def verify_webhook_signature(
    payload_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    # Calculate HMAC-SHA256
    expected_signature = hmac.new(
        key=secret.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(expected_signature, signature)
```

**Features**:
- ✅ HMAC-SHA256 (Razorpay standard)
- ✅ Constant-time comparison (timing attack protection)
- ✅ Takes raw bytes (not parsed JSON)

**Status**: ✅ **IMPLEMENTED AND TESTED**

**Tests**: 3 signature verification tests passing
- Valid signature
- Invalid signature
- Modified payload

---

## 5. Expected Environment Variable for Webhook Secret

**Variable name**: `RAZORPAY_WEBHOOK_SECRET`

**Usage**: Used by `WebhookHandler.__init__(webhook_secret: str)`

**Current .env.example**:
```bash
RAZORPAY_WEBHOOK_SECRET=
```

**Status**: ⚠️ Environment variable defined but not set

**Security**:
- ✅ Loaded from environment only
- ✅ Never logged
- ✅ Never in error messages

---

## 6. Supported Event Names

**Event types** (from `execution/types.py:25-28`):

| Event Type | Enum Value | Handler |
|------------|------------|---------|
| payment_link.paid | `WebhookEventType.PAYMENT_LINK_PAID` | `_handle_paid()` |
| payment_link.partially_paid | `WebhookEventType.PAYMENT_LINK_PARTIALLY_PAID` | `_handle_partially_paid()` |
| payment_link.cancelled | `WebhookEventType.PAYMENT_LINK_CANCELLED` | `_handle_cancelled()` |
| payment_link.expired | `WebhookEventType.PAYMENT_LINK_EXPIRED` | `_handle_expired()` |

**Event routing** (webhooks.py:183-198):
```python
if event_type == WebhookEventType.PAYMENT_LINK_PAID.value:
    self._handle_paid(webhook_event, execution, entity)
elif event_type == WebhookEventType.PAYMENT_LINK_PARTIALLY_PAID.value:
    self._handle_partially_paid(webhook_event, execution, entity)
elif event_type == WebhookEventType.PAYMENT_LINK_CANCELLED.value:
    self._handle_cancelled(webhook_event, execution, entity)
elif event_type == WebhookEventType.PAYMENT_LINK_EXPIRED.value:
    self._handle_expired(webhook_event, execution, entity)
else:
    # Unknown event type -> FAILED
```

**Status**: ✅ All 4 event types implemented and tested

---

## 7. payment_link.paid Resolution to Existing Execution

**Resolution method** (webhooks.py:158-166):

### Step 1: Extract identifiers from webhook payload
```python
payment_link_id = entity.get("id")           # Razorpay Payment Link ID
reference_id = entity.get("reference_id")     # RAY reference ID
```

### Step 2: Resolve execution (two-stage lookup)
```python
execution = None

# Try Payment Link ID first
if payment_link_id:
    execution = self.execution_service.get_execution_by_payment_link_id(payment_link_id)

# Fallback to reference_id
if not execution and reference_id:
    execution = self.execution_service.get_execution_by_reference_id(reference_id)

# If still not found -> FAILED
if not execution:
    return {"error": "Execution not found"}
```

### Step 3: Extract opportunity_id from execution
```python
opportunity_id = execution.opportunity_id
```

**Lookup methods**:
- `get_execution_by_payment_link_id()` - Match on Razorpay Payment Link ID
- `get_execution_by_reference_id()` - Match on deterministic RAY reference ID

**For plink_TUHmPcKkJIlbli**:
- Payment Link ID: `plink_TUHmPcKkJIlbli`
- Reference ID: `RAY-test_opp_1787722729-58379e45`
- Opportunity ID: `test_opp_1787722729`

**Status**: ✅ Resolution logic implemented and tested

**Blocker**: ⚠️ Execution records in-memory only (lost after process restart)

---

## 8. RecoveryOutcome Creation

**Handler**: `_handle_paid()` in webhooks.py:218-253

### Process for payment_link.paid

**Step 1**: Check for stale events
```python
current_state = self.execution_service.get_opportunity_state(opportunity_id)
if current_state == OpportunityState.RECOVERED.value:
    return  # Already recovered, ignore stale event
```

**Step 2**: Extract payment details
```python
payment_id = entity.get("payment_id")
amount_paid = entity.get("amount_paid", 0) / 100.0  # Convert from paise to rupees
```

**Step 3**: Create RecoveryOutcome
```python
outcome = RecoveryOutcome(
    outcome_id=str(uuid.uuid4()),
    opportunity_id=opportunity_id,
    execution_id=execution.execution_id,
    outcome_type=OutcomeType.RECOVERED.value,
    amount_recovered=amount_paid,
    currency=execution.currency,
    razorpay_payment_id=payment_id,
    razorpay_payment_link_id=execution.razorpay_payment_link_id,
    source_event_id=webhook_event.event_id,
    observed_at=datetime.now(timezone.utc).isoformat(),
    notes=None,
)
```

**Step 4**: Persist outcome
```python
self.recovery_outcomes[outcome.outcome_id] = outcome
```

**Step 5**: Update opportunity state
```python
self.execution_service.opportunity_states[opportunity_id] = OpportunityState.RECOVERED.value
```

**Status**: ✅ Fully implemented

**Fields tracked**:
- outcome_id (UUID)
- opportunity_id
- execution_id
- outcome_type (RECOVERED)
- amount_recovered (in rupees)
- currency
- razorpay_payment_id
- razorpay_payment_link_id
- source_event_id (webhook event ID)
- observed_at (timestamp)

---

## 9. Duplicate Event Handling

**Method**: Event ID tracking (webhooks.py:114-138)

### Implementation

**Step 1**: Extract event ID
```python
event_id = payload.get("id", payload.get("event"))
```

**Step 2**: Check if already processed
```python
if event_id in self.event_ids:
    # Duplicate event
    return {
        "success": True,
        "status": "duplicate",
        "message": "Event already processed"
    }
```

**Step 3**: Track new events
```python
self.event_ids.add(event_id)
```

**Idempotency mechanism**:
- Tracks processed event IDs in `self.event_ids` set
- Returns success without re-processing
- Records as `WebhookProcessingStatus.DUPLICATE`

**Storage**: In-memory set (lost after restart)

**Status**: ✅ Implemented and tested

**Test coverage**:
- Duplicate event detection
- Same payload sent twice
- Returns success on duplicate

---

## 10. Stale Event Handling

**Method**: State checking before updates

### Terminal State Protection

**Terminal states** (cannot be downgraded):
- `RECOVERED`
- `PARTIALLY_RECOVERED`

### Implementation by event type

**payment_link.paid** (webhooks.py:229-233):
```python
current_state = self.execution_service.get_opportunity_state(opportunity_id)
if current_state == OpportunityState.RECOVERED.value:
    return  # Already recovered, ignore stale event
```

**payment_link.expired** (webhooks.py:342-347):
```python
current_state = self.execution_service.get_opportunity_state(opportunity_id)
if current_state in [OpportunityState.RECOVERED.value, OpportunityState.PARTIALLY_RECOVERED.value]:
    return  # Already recovered, ignore expired event
```

**payment_link.cancelled** (webhooks.py:304-310):
```python
current_state = self.execution_service.get_opportunity_state(opportunity_id)
if current_state in [OpportunityState.RECOVERED.value, OpportunityState.PARTIALLY_RECOVERED.value]:
    return  # Already recovered, ignore cancelled event
```

**Protection examples**:
- `paid` → `expired` (late): Expired event ignored
- `paid` → `cancelled` (late): Cancelled event ignored
- `partially_paid` → `expired`: Expired event ignored

**Status**: ✅ Implemented and tested

**Tests**:
- Expired after recovered (ignored)
- Cancelled after recovered (ignored)

---

## 11. Starting the Local FastAPI Server

### Command

**From repository root**:
```bash
cd services/api
.venv/bin/python main.py
```

**OR with uvicorn directly**:
```bash
cd services/api
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**OR from repository root**:
```bash
services/api/.venv/bin/uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Environment setup required

**Before starting**:
1. Set environment variables:
   ```bash
   export RAZORPAY_MODE=test
   export RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
   export RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
   export RAZORPAY_WEBHOOK_SECRET=<your_webhook_secret>
   ```

2. OR use .env file (python-dotenv will load it)

### Server startup output

**Expected**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## 12. Server Port

**Port**: `8000`

**Configuration**: `services/api/main.py:172`
```python
uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=8000,
    reload=True,
    log_level="info"
)
```

**Access URLs**:
- Local: `http://localhost:8000`
- Health check: `http://localhost:8000/health`
- Webhook endpoint: `http://localhost:8000/webhooks/razorpay`

**CORS**: Enabled for `http://localhost:3000` (Next.js)

---

## 13. Development Tunnel Safety

### Can be exposed safely? ⚠️ **YES, with critical caveats**

**Tunnel options**:
- ngrok: `ngrok http 8000`
- Cloudflare Tunnel
- VS Code Port Forwarding
- localtunnel

**Security considerations**:

✅ **SAFE**:
- Signature verification implemented
- Invalid signatures rejected
- Test Mode only (no live charges)
- No credentials in responses

⚠️ **REQUIRED BEFORE TUNNEL**:
1. **Implement the webhook route** (currently returns 501)
2. **Set RAZORPAY_WEBHOOK_SECRET** (currently empty)
3. **Integrate WebhookHandler** with FastAPI route
4. **Test signature verification locally first**

❌ **RISKS WITHOUT IMPLEMENTATION**:
- Route returns 501 (webhooks will fail)
- Missing webhook secret (verification fails)
- Execution records in-memory (lost on restart)
- No persistence (can't recover from crashes)

**Recommendation**: ✅ Safe to expose AFTER implementation complete

---

## 14. Blockers to Testing plink_TUHmPcKkJIlbli

### BLOCKER 1: Webhook Route Not Implemented

**Issue**: FastAPI route returns 501 (Not Implemented)

**Impact**: Webhooks cannot be processed

**Required**:
```python
@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    # 1. Get raw body
    raw_body = await request.body()
    
    # 2. Get signature header
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    # 3. Parse JSON
    payload = await request.json()
    
    # 4. Get webhook secret
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    
    # 5. Initialize handler
    handler = WebhookHandler(execution_service, webhook_secret)
    
    # 6. Process webhook
    result = handler.process_webhook(raw_body, signature, payload)
    
    # 7. Return response
    return JSONResponse(content=result)
```

**Severity**: 🔴 **CRITICAL** - Must fix before testing

---

### BLOCKER 2: Execution Records Lost (In-Memory)

**Issue**: ExecutionService stores records in-memory only

**Impact**: 
- Execution record for plink_TUHmPcKkJIlbli lost after process restart
- Webhook cannot resolve Payment Link to execution
- Returns "Execution not found" error

**Current state**:
```python
# services/api/execution/service.py
class ExecutionService:
    def __init__(self, executor):
        self.executions = {}  # In-memory dict (lost on restart)
```

**For plink_TUHmPcKkJIlbli**:
- Execution ID: `f2ace481-f360-480a-b390-b365710944bc`
- Payment Link ID: `plink_TUHmPcKkJIlbli`
- Reference ID: `RAY-test_opp_1787722729-58379e45`

**Required**:
- Re-run test script to recreate execution record (BUT Payment Link already exists!)
- OR implement database persistence
- OR manually seed execution record before webhook test

**Severity**: 🔴 **CRITICAL** - Cannot test without execution record

---

### BLOCKER 3: Webhook Secret Not Set

**Issue**: `RAZORPAY_WEBHOOK_SECRET` not set in .env

**Impact**: Signature verification will fail

**Current .env**:
```bash
RAZORPAY_WEBHOOK_SECRET=
```

**Required**: Get webhook secret from Razorpay dashboard

**Steps**:
1. Log into Razorpay Dashboard (Test Mode)
2. Go to Settings → Webhooks
3. Create webhook pointing to public URL
4. Copy webhook secret
5. Set in .env: `RAZORPAY_WEBHOOK_SECRET=<secret>`

**Severity**: 🔴 **CRITICAL** - Webhooks will be rejected

---

### BLOCKER 4: No Public URL for Local Server

**Issue**: Razorpay needs public URL to send webhooks

**Impact**: Cannot receive webhooks from Razorpay

**Current**: `localhost:8000` (not publicly accessible)

**Required**: Expose via tunnel
- ngrok: `ngrok http 8000`
- Provides: `https://<random>.ngrok.io`

**Webhook URL**: `https://<random>.ngrok.io/webhooks/razorpay`

**Severity**: 🟡 **HIGH** - Easy to fix with tunnel

---

### BLOCKER 5: Execution Record Idempotency Conflict

**Issue**: plink_TUHmPcKkJIlbli already created in Razorpay

**Impact**: Cannot re-run test script to recreate execution record

**Error** (if re-run):
```
payment link with given reference_id: RAY-test_opp_1787722729-58379e45 already exists
```

**Options**:
1. **Manual seed**: Create execution record in memory before starting server
2. **Database persistence**: Persist execution, survive restarts
3. **Use existing link**: Trigger webhook manually from Razorpay dashboard

**Severity**: 🟡 **HIGH** - Workaround available

---

### Summary of Blockers

| # | Blocker | Severity | Can Workaround? |
|---|---------|----------|-----------------|
| 1 | Webhook route not implemented | 🔴 Critical | No - Must implement |
| 2 | Execution records in-memory | 🔴 Critical | Yes - Manual seed |
| 3 | Webhook secret not set | 🔴 Critical | Yes - Get from dashboard |
| 4 | No public URL | 🟡 High | Yes - Use ngrok |
| 5 | Cannot recreate execution | 🟡 High | Yes - Manual seed |

**Can test webhooks today?** ⚠️ **NO** - Must fix blockers 1, 2, 3 first

---

## Recommended Next Steps

### Immediate (Required for webhook testing)

1. **Implement webhook route** (15 minutes)
   - Integrate WebhookHandler with FastAPI
   - Capture raw body
   - Extract signature header
   - Call handler.process_webhook()

2. **Get webhook secret** (5 minutes)
   - Access Razorpay Test Mode dashboard
   - Copy webhook secret
   - Set RAZORPAY_WEBHOOK_SECRET in .env

3. **Seed execution record** (10 minutes)
   - Create script to manually seed ExecutionService
   - Populate with plink_TUHmPcKkJIlbli details
   - Keep server running (don't restart)

4. **Expose server via tunnel** (2 minutes)
   - Run: `ngrok http 8000`
   - Copy public URL

5. **Configure Razorpay webhook** (5 minutes)
   - Add webhook in Razorpay dashboard
   - Point to: `https://<ngrok-url>/webhooks/razorpay`
   - Select events: payment_link.paid, etc.

### Later (For production)

6. **Database persistence**
   - Persist ExecutionAttempt to database
   - Persist WebhookEvent to database
   - Persist RecoveryOutcome to database

7. **Webhook retry handling**
   - Handle Razorpay webhook retries
   - Idempotency across restarts

---

## Testing Plan for plink_TUHmPcKkJIlbli

**Payment Link**: plink_TUHmPcKkJIlbli  
**URL**: https://rzp.io/rzp/DzGMunk

### Prerequisites

- [ ] Webhook route implemented
- [ ] Webhook secret set
- [ ] Execution record seeded
- [ ] Server running
- [ ] ngrok tunnel active
- [ ] Razorpay webhook configured

### Test Flow

1. **Open Payment Link** in browser
2. **Complete payment** using Razorpay test card
3. **Razorpay sends** payment_link.paid webhook
4. **Server receives** webhook at `/webhooks/razorpay`
5. **Signature verified** (HMAC-SHA256)
6. **Event processed** by WebhookHandler
7. **RecoveryOutcome created** (RECOVERED)
8. **Opportunity state updated** (RECOVERED)

### Expected Result

**Webhook response**:
```json
{
  "success": true,
  "webhook_id": "<uuid>",
  "event_type": "payment_link.paid",
  "opportunity_id": "test_opp_1787722729"
}
```

**Recovery outcome**:
- outcome_type: RECOVERED
- amount_recovered: ₹100.0
- razorpay_payment_id: pay_<id>
- opportunity state: RECOVERED

---

## Configuration Summary

**Environment variables required**:
```bash
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=<get_from_dashboard>
```

**Server**: `http://localhost:8000`  
**Webhook endpoint**: `POST /webhooks/razorpay`  
**Status**: ⚠️ Not implemented (returns 501)

**WebhookHandler**: ✅ Implemented and tested  
**Signature verification**: ✅ Implemented and tested  
**Event processing**: ✅ Implemented and tested  

**Integration**: ❌ Not connected to FastAPI route

---

**Report Complete**  
**Status**: Cannot test webhooks until blockers resolved  
**Recommendation**: Implement webhook route integration before proceeding
