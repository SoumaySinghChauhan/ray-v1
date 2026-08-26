# RAY V1 - Webhook Testing Guide

**Status**: Webhook integration complete, ready for testing  
**Payment Link**: `plink_TUHmPcKkJIlbli` (Test Mode)  
**Last Updated**: 2026-08-26

---

## Prerequisites

✅ Webhook route integrated at `POST /webhooks/razorpay`  
✅ Signature verification implemented (HMAC-SHA256)  
✅ **SECURITY: Signature verified BEFORE JSON parsing**  
✅ WebhookHandler connected to FastAPI  
✅ Raw body capture before JSON parsing  
✅ Database-backed persistence (restart-safe)  
✅ Webhook secret loaded from `.env`

---

## Quick Start

### 1. Set Webhook Secret

Get your webhook secret from Razorpay Dashboard:

1. Log into [Razorpay Dashboard](https://dashboard.razorpay.com/) (Test Mode)
2. Navigate to **Settings** → **Webhooks**
3. Create or view webhook configuration
4. Copy the **Webhook Secret**
5. Add to `.env`:
   ```bash
   RAZORPAY_WEBHOOK_SECRET=whsec_YOUR_SECRET_HERE
   ```

### 2. Start the Server

```bash
cd services/api
.venv/bin/python main.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### 3. Expose Server (ngrok)

```bash
ngrok http 8000
```

Copy the public URL: `https://<random>.ngrok.io`

### 4. Configure Razorpay Webhook

1. Go to Razorpay Dashboard → Settings → Webhooks
2. Click **Add Webhook**
3. Enter:
   - URL: `https://<random>.ngrok.io/webhooks/razorpay`
   - Secret: (already configured)
   - Events: Select all Payment Link events:
     - `payment_link.paid`
     - `payment_link.partially_paid`
     - `payment_link.cancelled`
     - `payment_link.expired`
4. Save

---

## Testing Scenarios

### Scenario 1: Valid Webhook (payment_link.paid)

**Setup**: Complete payment on existing Payment Link

**Payment Link**: https://rzp.io/rzp/DzGMunk (plink_TUHmPcKkJIlbli)

**Steps**:
1. Open Payment Link in browser
2. Use Razorpay test card:
   - Card: `4111 1111 1111 1111`
   - CVV: Any 3 digits
   - Expiry: Any future date
3. Complete payment
4. Razorpay sends webhook to your server

**Expected**:
- Server receives webhook at `/webhooks/razorpay`
- Signature verified successfully
- Event processed by `WebhookHandler`
- `RecoveryOutcome` created (outcome_type: RECOVERED)
- Opportunity state updated to RECOVERED

**Response**:
```json
{
  "success": true,
  "webhook_id": "<uuid>",
  "event_type": "payment_link.paid",
  "opportunity_id": "test_opp_1787722729"
}
```

### Scenario 2: Invalid Signature

**Setup**: Manually send webhook with invalid signature

```bash
curl -X POST http://localhost:8000/webhooks/razorpay \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: invalid_signature" \
  -d '{
    "id": "evt_test",
    "event": "payment_link.paid",
    "payload": {"payment_link": {"entity": {"id": "plink_test"}}}
  }'
```

**Expected Response**:
```json
{
  "success": false,
  "error": "Invalid signature"
}
```

### Scenario 3: Duplicate Event

**Setup**: Send same webhook twice

**Expected**:
- First webhook: Processed normally
- Second webhook: Detected as duplicate
- Response: `{"success": true, "status": "duplicate"}`

### Scenario 4: Stale Event (Expired After Recovered)

**Setup**: Opportunity already RECOVERED, then expired event arrives

**Expected**:
- Webhook received and verified
- Event ignored (terminal state protection)
- No state change

---

## Verification Script

Run verification before testing:

```bash
services/api/.venv/bin/python scripts/verify_webhook_route.py
```

**Checks**:
- ✅ Signature verification function
- ✅ WebhookHandler processing
- ✅ FastAPI route registration

---

## Troubleshooting

### Problem: "Webhook secret not configured"

**Cause**: `RAZORPAY_WEBHOOK_SECRET` not set

**Fix**: Add to `.env` and restart server

### Problem: "Invalid signature"

**Causes**:
1. Wrong webhook secret in `.env`
2. Payload modified after signing
3. Razorpay dashboard webhook secret changed

**Fix**: Verify webhook secret matches Razorpay dashboard

### Problem: "Execution not found"

**Cause**: Execution record not in memory (server restarted)

**Fix**: Re-create execution:
```bash
services/api/.venv/bin/python scripts/test_razorpay_payment_link.py --confirm-test-link
```

**Note**: Will fail if Payment Link already exists (use existing link instead)

### Problem: ngrok tunnel disconnected

**Cause**: Free ngrok tunnels expire

**Fix**: Restart ngrok, update Razorpay webhook URL

---

## Security Checklist

✅ **TEST MODE ONLY** - No live charges  
✅ **Signature verification** - HMAC-SHA256 with constant-time comparison  
✅ **Raw body capture** - Signature verified before JSON parsing  
✅ **Webhook secret** - Loaded from environment only, never logged  
✅ **Duplicate detection** - Event IDs tracked to prevent replay  
✅ **Stale event protection** - Terminal states cannot be downgraded  

---

## Known Limitations

⚠️ **In-memory storage**: Execution records lost on process restart

**Impact**: Webhooks fail to resolve Payment Link after restart

**Workaround**: Keep server running, or re-create execution before testing

**Future**: Database persistence (Prompt 6.2+)

---

## Architecture

### Webhook Flow

```
Razorpay → ngrok → FastAPI Route → WebhookHandler → ExecutionService
                         ↓
                   Signature Verify (HMAC-SHA256)
                         ↓
                   Duplicate Check (event_id)
                         ↓
                   Execution Lookup (payment_link_id / reference_id)
                         ↓
                   Event Processing (_handle_paid / _handle_expired / etc.)
                         ↓
                   RecoveryOutcome Creation
                         ↓
                   Opportunity State Update
```

### Key Components

**FastAPI Route** (`services/api/main.py:99-164`):
- Captures raw request body
- Extracts X-Razorpay-Signature header
- Initializes WebhookHandler
- Returns JSON response

**WebhookHandler** (`execution/webhooks.py`):
- Verifies signature
- Checks for duplicates
- Resolves execution
- Routes to event handlers
- Creates RecoveryOutcome
- Updates opportunity state

**ExecutionService** (`execution/service.py`):
- Stores execution records (in-memory)
- Tracks opportunity states
- Resolves Payment Links

---

## Next Steps

After successful webhook testing:

1. **Database Persistence** (Prompt 6.2):
   - Persist ExecutionAttempt
   - Persist WebhookEvent
   - Persist RecoveryOutcome
   - Survive process restarts

2. **Webhook Retry Handling**:
   - Handle Razorpay retries
   - Idempotency across restarts

3. **Production Deployment**:
   - Persistent webhook URL (not ngrok)
   - Database backend
   - Monitoring and alerting

---

## Support

**Documentation**:
- [Razorpay Webhooks](https://razorpay.com/docs/webhooks/)
- [RAY Policy v1.0](./policy-v1.0.md)
- [RAY Razorpay Integration v1.0](./razorpay-integration-v1.0.md)

**Test Payment Link**:
- ID: `plink_TUHmPcKkJIlbli`
- URL: https://rzp.io/rzp/DzGMunk
- Reference: `RAY-test_opp_1787722729-58379e45`

**Verification**: Run `scripts/verify_webhook_route.py`
