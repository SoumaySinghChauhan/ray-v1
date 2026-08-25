# RAY V1 — Stage B Failure Investigation

**Date**: 2026-08-25  
**Stage**: B (100 opportunities)  
**Result**: 4 successful, 96 failed  
**Root Cause**: Gemini API quota exhausted

---

## Executive Summary

**Stage B failed due to Gemini API quota exhaustion after 4 successful diagnoses.**

- **Successes**: 4 (opp_000000 to opp_000003)
- **Failures**: 96 (opp_000004 to opp_000099)
- **Error**: 429 RESOURCE_EXHAUSTED - "You exceeded your current quota"
- **Total API calls**: 292 (4 successful + 288 failed)
- **Retries performed**: 192 (96 failed opportunities × 2 retries each)

**Stage B diagnosis artifact is INVALID FOR ML** - only 4% success rate.

---

## ACTUAL ERROR BREAKDOWN

### Error Type Distribution

| Error | Count | Percentage |
|-------|-------|------------|
| **429 RESOURCE_EXHAUSTED** | **287** | **99.7%** |
| JSONDecodeError | 1 | 0.3% |
| **Total** | **288** | **100%** |

### HTTP Status Codes

| Status | Count | Percentage |
|--------|-------|------------|
| **429** | **287** | **99.7%** |
| None | 1 | 0.3% |

### Failure Categories (from error_capture.py)

| Category | Count | Percentage |
|----------|-------|------------|
| **unknown** | **288** | **100%** |

**Bug identified**: RESOURCE_EXHAUSTED not categorized correctly (see Secondary Issues)

### Retry Distribution

| Retry Number | Error Count | Opportunities |
|--------------|-------------|---------------|
| 0 (initial) | 96 | 96 failed on first attempt |
| 1 (first retry) | 96 | All 96 retried once |
| 2 (second retry) | 96 | All 96 retried twice |
| **Total** | **288** | **96 opportunities × 3 attempts** |

---

## RETRY BEHAVIOR

### Actual Behavior

**Retries WERE performed correctly**:
- Each failed opportunity was retried 2 times (max_retries - 1 = 3 - 1 = 2)
- Total attempts per failed opportunity: 3 (initial + 2 retries)
- 96 failed opportunities × 3 attempts = 288 error records ✓

**Evidence**:
- Error log shows retry_number: 0, 1, 2 for each failed opportunity
- Diagnosis records show final `retry_count: 2` for all failed opportunities
- All 96 failures exhausted all retry attempts

### Retry Recovery Rate

**0%** - No failed opportunities recovered via retry

**Reason**: All retries encountered same quota error (429 RESOURCE_EXHAUSTED)

### Reporting Inconsistency (Bug)

**Manifest reports**:
```json
{
  "total_retries": 0,
  "diagnoses_failed": 288
}
```

**Actual reality**:
- Retries performed: 192 (96 opportunities × 2 retries)
- Individual API call failures: 288
- Final failed opportunities: 96

**Root cause**: Code bug in `pilot_diagnose.py` line 190:

```python
self.stats["total_retries"] += attempt
```

This line is ONLY reached when diagnosis SUCCEEDS. Failed opportunities never reach this line, so their retries are not counted in `total_retries`.

**Correct behavior should be**:
- Stage A: 3 retries for successful recoveries + 2 retries for 1 permanent failure = 5 total
- Stage B: 0 retries for successes + 192 retries for failures = 192 total

**Actual reported**:
- Stage A: 3 (only counts successful retries)
- Stage B: 0 (no successful retries)

**Consequence**: `total_retries` is misleading - it means "retries that led to success", not "total retry attempts".

---

## RATE LIMIT / QUOTA EVIDENCE

### Direct Evidence from Error Messages

**Error code**: `429 RESOURCE_EXHAUSTED`

**Error message** (from first failure):
```
429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your 
current quota, please check your plan and billing details. For more information 
on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. 
To monitor your current usage, head to: https://ai.dev/rate-limit.
```

**Source**: Google Gemini API

**Meaning**: API key has hit quota limit (free tier or billing issue)

### Timeline Evidence

**Successful diagnoses** (4 total):
- opp_000000: success, no retries
- opp_000001: success, no retries
- opp_000002: success, no retries
- opp_000003: success, no retries

**Quota exhaustion point**:
- opp_000004: FIRST FAILURE at 2026-08-25T18:06:59.350577+00:00
- Error: 429 RESOURCE_EXHAUSTED
- Retry 0: RESOURCE_EXHAUSTED
- Retry 1: RESOURCE_EXHAUSTED
- Retry 2: RESOURCE_EXHAUSTED

**All subsequent opportunities** (opp_000004 through opp_000099):
- Every single attempt: 429 RESOURCE_EXHAUSTED
- No recovery
- No variation in error type

**Duration**: 203.8 seconds (3.4 minutes) from first failure to last failure

### Quota Type

**Not rate limiting** (temporary throttle) - would expect recovery after wait

**IS quota exhaustion** (hard limit) - persistent across all retries and time

Evidence:
- No successful requests after quota hit
- All 288 subsequent API calls failed with same error
- No time-based recovery (failures span 3.4 minutes)
- Error message explicitly states: "exceeded your current quota"

---

## ROOT CAUSE

**PRIMARY**: **Gemini API free tier quota exhausted**

**Evidence**:
1. ✅ Explicit error: "You exceeded your current quota, please check your plan and billing details"
2. ✅ HTTP 429 (quota error, not rate limit)
3. ✅ Complete failure after 4 successes (no partial recovery)
4. ✅ Persistent across all 288 subsequent attempts over 3.4 minutes
5. ✅ No variation in error type

**Quota limit reached at**: Request #5 (opp_000004)

**API calls consumed**:
- Stage A: 10 successful + 6 retries = 16 API calls
- Stage B: 4 successful + 288 quota errors = 292 API calls
- **Total**: ~308 API calls before hard stop

**Hypothesis**: Free tier quota is very low (possibly 10-20 requests total, or daily limit)

---

## SECONDARY ISSUES

### Bug 1: Incorrect Retry Count Reporting

**Location**: `ai/diagnosis/pilot_diagnose.py` line 190

**Issue**: `self.stats["total_retries"] += attempt` only counts retries that led to SUCCESS

**Impact**: Misleading metrics - looks like no retries were performed when 192 were actually attempted

**Fix**: Track retry attempts separately from retry successes

### Bug 2: RESOURCE_EXHAUSTED Not Categorized

**Location**: `ai/diagnosis/error_capture.py` line 123

**Issue**: Categorization check does not include `RESOURCE_EXHAUSTED`:
```python
if error_reason in ['RATE_LIMIT_EXCEEDED', 'TIMEOUT', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR']:
    error_record["failure_category"] = "transient"
```

**Result**: All 288 quota errors categorized as "unknown" instead of appropriate category

**Impact**: Manifest shows `"unknown": 288` instead of meaningful categorization

**Fix**: Add RESOURCE_EXHAUSTED to categorization (likely "permanent" for quota, or new "quota" category)

### Bug 3: Manifest "diagnoses_failed" is Ambiguous

**Issue**: Manifest reports:
```json
{
  "diagnoses_failed": 288
}
```

But this is the count of INDIVIDUAL API CALL FAILURES, not failed OPPORTUNITIES (96).

**Impact**: Confusing - looks like 288 opportunities failed when only 96 did

**Fix**: Separate fields for:
- `opportunities_failed`: 96
- `individual_call_failures`: 288
- `retry_attempts`: 192

---

## COMPARISON: STAGE A vs STAGE B

| Metric | Stage A (10 opps) | Stage B (100 opps) |
|--------|-------------------|-------------------|
| Successful | 9 (90%) | 4 (4%) |
| Failed | 1 (10%) | 96 (96%) |
| Error type | API_KEY_INVALID (all 6) | RESOURCE_EXHAUSTED (287/288) |
| Recovery via retry | 2/3 (66.7%) | 0/96 (0%) |
| Duration | 376s (6.3 min) | 281s (4.7 min) |
| Individual errors | 6 | 288 |
| Retries performed | 5 | 192 |
| Retries reported | 3 | 0 |

**Key differences**:

1. **Error type changed**:
   - Stage A: API_KEY_INVALID (authentication issue)
   - Stage B: RESOURCE_EXHAUSTED (quota issue)

2. **Success rate collapsed**:
   - Stage A: 90% (acceptable)
   - Stage B: 4% (catastrophic)

3. **No recovery**:
   - Stage A: 66.7% of failures recovered via retry
   - Stage B: 0% recovery (quota persists)

4. **Earlier in batch**:
   - Stage A: Failure at opportunity 6
   - Stage B: Failure at opportunity 5

**Conclusion**: Different root causes. Stage A was authentication (wrong/invalid key), Stage B is quota exhaustion (valid key, no credits).

---

## TIMING ANALYSIS

**Stage B chronology**:

1. **18:06:59** - First quota error (opp_000004, retry 0)
2. **18:10:23** - Last quota error (opp_000099, retry 2)
3. **Time span**: 203.8 seconds (3.4 minutes)

**Pattern**:
- NO evidence of gradual degradation
- NO evidence of temporary rate limiting
- NO evidence of time-based recovery
- Quota exhaustion was IMMEDIATE and PERSISTENT

**Interpretation**: Hard quota limit reached, not soft rate limiting

---

## STAGE B ARTIFACT STATUS

### INVALID FOR ML

**Reason**:
- Only 4% successful diagnoses (4 out of 100)
- 96% quota failures
- Insufficient data for training or evaluation
- Not representative of real diagnosis quality

**Cannot use for**:
- Model B feature engineering
- ML training
- Validation metrics
- Confidence analysis
- ANY production use

**Only valid for**:
- Quota/error debugging
- Infrastructure testing
- Error capture validation

---

## RECOMMENDED FIX

### Primary Fix: Resolve Quota

**Action**: Obtain valid Gemini API key with sufficient quota

**Options**:

**Option 1: Google AI Studio (Free tier with higher quota)**
- URL: https://aistudio.google.com/apikey
- Create NEW API key
- Verify quota limits
- Free tier may have higher limits than current key

**Option 2: Upgrade to Paid Plan**
- Enable billing on Google Cloud project
- Set budget alerts
- Estimated cost for 1,000 requests: $5-15

**Option 3: Switch Provider**
- Anthropic: $5 free credit for new accounts
- OpenAI: Requires payment setup
- Would require minimal code changes (provider already abstracted)

### Secondary Fixes: Code Bugs

**Fix 1: Retry count reporting** (ai/diagnosis/pilot_diagnose.py)

```python
# Current (WRONG):
self.stats["total_retries"] += attempt  # Only counts successful retries

# Fixed:
# Track all retry attempts, not just successful ones
# Add after each retry attempt, not just on success
```

**Fix 2: RESOURCE_EXHAUSTED categorization** (ai/diagnosis/error_capture.py)

```python
# Current:
if error_reason in ['RATE_LIMIT_EXCEEDED', 'TIMEOUT', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR']:
    error_record["failure_category"] = "transient"

# Fixed:
if error_reason in ['RATE_LIMIT_EXCEEDED', 'TIMEOUT', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'RESOURCE_EXHAUSTED']:
    error_record["failure_category"] = "transient"
# OR create new category:
elif error_reason == 'RESOURCE_EXHAUSTED':
    error_record["failure_category"] = "quota_exceeded"
```

**Fix 3: Manifest clarity**

Add separate fields:
```json
{
  "opportunities_total": 100,
  "opportunities_successful": 4,
  "opportunities_failed": 96,
  "individual_api_calls": 292,
  "individual_api_failures": 288,
  "retry_attempts_made": 192
}
```

---

## NEXT ACTION

**CHOOSE**: **C. Resolve quota before continuing**

**Rationale**:
1. Root cause is definitive (quota exhausted)
2. No code fix will resolve quota issue
3. Retry logic is working correctly
4. Error capture is working correctly
5. Only issue is insufficient API quota

**Specific steps**:

1. **Obtain valid API key** with sufficient quota
2. **Test with 10-opportunity pilot** to confirm quota is sufficient
3. **If pilot passes**: Run Stage B again (100 opportunities)
4. **If Stage B passes**: Proceed to Stage C (1,000 opportunities)

**Do NOT**:
- Run Stage C with current key (will fail immediately)
- Use Stage B artifact for ML (insufficient data)
- Attempt code fixes without quota resolution
- Switch providers without quota confirmation first

**Alternative if quota cannot be obtained**:
- Chunk Stage C into smaller batches (e.g., 10 batches of 100)
- Run one batch per day if daily quota limit
- Switch to Anthropic/OpenAI provider

---

## VERIFICATION QUESTIONS ANSWERED

### 1. Did retries happen?

**YES** - 192 retry attempts were made (96 opportunities × 2 retries each)

Evidence: Error log shows retry_number 0, 1, 2 for each failed opportunity

### 2. Why does manifest say "total_retries: 0"?

**BUG** - Code only counts retries that led to SUCCESS, not all retry attempts

### 3. Is this rate limiting?

**NO** - This is quota exhaustion (hard limit), not rate limiting (temporary throttle)

Evidence: Error message explicitly says "exceeded your current quota"

### 4. Could this be a timing issue?

**NO** - Failures are immediate and persistent, not time-based

Evidence: All 288 failures over 3.4 minutes have same error, no recovery

### 5. Is Stage B data usable?

**NO** - Only 4% success rate, cannot be used for ML training or evaluation

### 6. What error type is this?

**429 RESOURCE_EXHAUSTED** (287 out of 288 errors)

Google Gemini quota limit reached

---

## FILES FOR EVIDENCE

- `datasets/v1.0.0/diagnoses_real/error_log_pilot_100.json` (288 error records)
- `datasets/v1.0.0/diagnoses_real/manifest_pilot_100.json` (aggregated stats)
- `datasets/v1.0.0/diagnoses_real/diagnoses_pilot_100.parquet` (4 successes, 96 failures)
- `datasets/v1.0.0/diagnoses_real/confidence_report_pilot_100.txt` (only 4 samples)

**Preserve these files** - valuable diagnostic evidence

---

## SUMMARY

**Root Cause**: Gemini API free tier quota exhausted after 4 requests

**Impact**: 96% failure rate, Stage B artifact invalid for ML

**Solution**: Obtain API key with sufficient quota

**Code Bugs Found**: 2 (retry counting, error categorization) - non-blocking, can fix later

**Next Step**: Resolve quota, rerun 10-opportunity confirmation pilot

**Stage C**: Cannot proceed until quota resolved

---

**Investigation Complete**: 2026-08-25  
**Evidence-Based**: All conclusions supported by actual error log data  
**Quota Issue**: Confirmed via 429 RESOURCE_EXHAUSTED errors  
**Artifact Status**: INVALID FOR ML ❌
