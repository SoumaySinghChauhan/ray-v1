# RAY V1 — Local Ollama Stage B Schema Failure Investigation

**Date**: 2026-08-26  
**Stage**: B (100 opportunities)  
**Provider**: Local (Ollama)  
**Model**: qwen3:4b-instruct  
**Result**: 99 successful, 1 failed

---

## Executive Summary

**Stage B local diagnosis completed with 99% success rate (99/100).**

**Schema failures**: 1 opportunity (opp_000026) failed 3 times (initial + 2 retries)

**Root cause**: Model generated invalid enum value `"HIGHER_VALUE_PAYMENT"` instead of valid `"HIGH_VALUE_PAYMENT"`

**Impact**: 1% failure rate, deterministic model behavior issue

**Recommendation**: **B. Keep current behavior and proceed to 1,000** (with documentation of known edge case)

---

## 1. SCHEMA FAILURE DETAILS

### Failed Opportunity

**Opportunity**: `opp_000026`  
**Customer**: `cust_000227`  
**Attempts**: 3 (initial + 2 retries)  
**Status**: All 3 attempts failed with identical error

### Raw Error

**Exception type**: `ValidationError`

**Error message**:
```
1 validation error for LLMDiagnosticOutput
reason_codes.2
  Input should be 'ISSUER_DECLINE', 'TEMPORARY_FAILURE', 'LIKELY_TRANSIENT', 
  'PERSISTENT_FAILURE', 'AUTHENTICATION_ISSUE', 'GATEWAY_ISSUE', 
  'STRONG_PAYMENT_HISTORY', 'WEAK_PAYMENT_HISTORY', 'RECENT_FAILURE_PATTERN', 
  'HIGH_RECOVERY_HISTORY', 'LOW_RECOVERY_HISTORY', 'HIGH_VALUE_PAYMENT', 
  'LOW_VALUE_PAYMENT', 'PAYMENT_METHOD_SIGNAL', 'LOW_CONTEXT_CONFIDENCE' 
  or 'INSUFFICIENT_INFORMATION' 
  [type=enum, input_value='HIGHER_VALUE_PAYMENT', input_type=str]
```

### Response Shape

**JSON parsing**: ✅ Succeeded (valid JSON)

**Schema validation**: ❌ Failed (invalid enum value)

**Field analysis**:
- `diagnostic_class`: Valid (present and correct enum)
- `reason_codes`: Invalid enum at index 2
  - reason_codes[0]: Valid
  - reason_codes[1]: Valid
  - reason_codes[2]: **'HIGHER_VALUE_PAYMENT'** (INVALID)
- `diagnostic_summary`: Valid (present and correct format)
- `confidence`: Valid (present and in range)

**Extra fields**: None

**Missing fields**: None

**Markdown/code fences**: No

**Explanatory text**: No

---

## 2. FAILURE CLASSIFICATION

### Root Cause

**Category**: **Valid JSON / Invalid enum**

**Specific issue**: Model generated creative but invalid enum value

**What happened**:
1. Model received opportunity with payment amount 1.59× customer average
2. Model correctly identified this as "higher than average value"
3. Model generated enum: `"HIGHER_VALUE_PAYMENT"` (creative description)
4. Valid enum is: `"HIGH_VALUE_PAYMENT"` (constrained vocabulary)

**Why it failed**:
- Model did not strictly follow enum constraints
- Model used similar but incorrect terminology
- Model was "helpful" but not "compliant"

**Pattern**:
- This is a **deterministic model behavior** issue
- Same opportunity → same invalid output (all 3 attempts)
- Model consistently chose wrong enum for this specific context

### Failure Categories (from list)

- ❌ Malformed JSON
- ✅ **Valid JSON / Invalid schema** ← ROOT CAUSE
- ❌ Missing field
- ✅ **Invalid enum** ← SPECIFIC ISSUE
- ❌ Invalid reason code (it IS a reason code, just wrong one)
- ❌ Invalid confidence
- ❌ Unexpected extra content
- ❌ Truncation
- ❌ Ollama/runtime issue
- ❌ Parser bug

---

## 3. RETRY BEHAVIOR

### Retry Trigger

✅ **Schema failures DID trigger retries**

**Evidence**:
- opp_000026 had 3 error records
- retry_number: 0, 1, 2
- Final diagnosis shows `retry_count: 2`

### Retry Configuration

**Current behavior**:
- Schema failures are treated as retryable errors
- Same as API failures (both use retry loop)
- Max retries: 3 attempts total (initial + 2 retries)

**Code location**: `ai/diagnosis/pilot_diagnose.py`

```python
except ValidationError as e:
    self.stats["schema_failed"] += 1
    # Capture error
    error_record = capture_api_error(...)
    self.error_log.append(error_record)
    
    if attempt == self.max_retries - 1:
        return self._create_failed_record(...)
    # Otherwise: continue to next retry
```

### Retry Effectiveness

**Prompt used**: Same prompt on all retries (no modification)

**Recovery rate**: 0% for this case

**Why retries failed**:
- Model behavior is deterministic for this specific input
- Same opportunity + same prompt + same model → same output
- No randomization or prompt variation between retries

**Comparison**:
- API failures (transient): Retries may help (network/service issues)
- Schema failures (deterministic model): Retries unlikely to help (same input → same output)

### Implementation Classification

**API failure vs Schema failure**: ✅ **Separate failure classes**

**Evidence**:
```python
self.stats["schema_failed"] += 1  # Schema counter
self.stats["llm_failed"] += 1     # API counter
```

**Both trigger retries**: Yes (both use same retry loop)

**Tracking**: Separate counters, but same retry behavior

---

## 4. OPPORTUNITY CONTEXT

### Why This Opportunity Failed

**Payment characteristics**:
- Amount: ₹5,321.25
- Customer average: ₹3,338.92
- **Ratio**: 1.59× average (significantly higher)

**Customer history**:
- Historical payments: 24
- Success rate: 11/24 (45.8%)
- Recovery rate: 23.08%
- Lifetime value: ₹34,394.93

**Failure type**:
- Canonical class: `soft_decline`
- Description: "Insufficient funds"

**Why model chose "HIGHER_VALUE_PAYMENT"**:
1. Model correctly identified payment is above average
2. Model wanted to express "higher than usual"
3. Valid enum `HIGH_VALUE_PAYMENT` means "high absolute value"
4. Model created `HIGHER_VALUE_PAYMENT` to mean "higher than customer's usual"
5. This is semantically reasonable but syntactically invalid

**Model reasoning** (inferred):
- `HIGH_VALUE_PAYMENT` = high in absolute terms
- `HIGHER_VALUE_PAYMENT` = higher than customer's baseline
- Model differentiated these concepts but only first exists in schema

---

## 5. QUALITY ASSESSMENT

### Success Metrics

| Metric | Value |
|--------|-------|
| Total opportunities | 100 |
| Successful | 99 |
| Failed | 1 |
| **Success rate** | **99.0%** |
| Schema failures | 1 (3 attempts) |
| LLM/API failures | 0 |

### Unique Summaries

**Count**: 99/99 unique

✅ **All successful diagnoses have unique summaries**

**No repetition or boilerplate detected**

### Diagnostic Class Distribution

| Class | Count | Percentage |
|-------|-------|------------|
| SOFT_DECLINE | 48 | 48.5% |
| HARD_DECLINE | 35 | 35.4% |
| AUTHENTICATION_FAILURE | 10 | 10.1% |
| GATEWAY_ERROR | 6 | 6.1% |

✅ **Good distribution across 4 classes**

**Note**: UNKNOWN class not used (all diagnoses were classified)

### Confidence Distribution

| Statistic | Value |
|-----------|-------|
| Min | 0.750 |
| Q25 | 0.850 |
| Median | 0.920 |
| Mean | 0.906 |
| Q75 | 0.950 |
| Max | 0.950 |
| **Unique values** | **6** |

✅ **Good variation** (6 unique values vs 2 in 10-case pilot)

**Values**: 0.75, 0.80, 0.85, 0.90, 0.92, 0.95

### Reason Code Coverage

**Unique codes used**: 12 out of 16 available

✅ **Good coverage** (75% of available vocabulary)

**Most common**:
- ISSUER_DECLINE
- PERSISTENT_FAILURE / TEMPORARY_FAILURE
- WEAK_PAYMENT_HISTORY / STRONG_PAYMENT_HISTORY
- HIGH_VALUE_PAYMENT / LOW_VALUE_PAYMENT

### Latency

| Metric | Value |
|--------|-------|
| Mean | 13.2s |
| Median | 12.7s |
| Min | 10.4s |
| Max | 21.1s |

✅ **Stable and fast** (faster than 10-case pilot: 16.1s → 13.2s)

**Projected for 1000**: ~3.7 hours (vs 4.5 hours estimated)

---

## 6. PROMPT ANALYSIS

### Current Prompt Structure

**System prompt** includes:
- Diagnostic classes with descriptions
- Confidence scoring guidance
- Example output format

**What's included**:
```
DIAGNOSTIC CLASSES:
SOFT_DECLINE: Temporary, potentially recoverable failures
HARD_DECLINE: Persistent, structural failures
AUTHENTICATION_FAILURE: Authentication/verification issues
GATEWAY_ERROR: Payment gateway/processing issues
UNKNOWN: Insufficient information

Example output:
{
  "diagnostic_class": "SOFT_DECLINE",
  "reason_codes": ["TEMPORARY_FAILURE", "STRONG_PAYMENT_HISTORY"],
  "diagnostic_summary": "...",
  "confidence": 0.85
}
```

**What's NOT explicitly listed**:
- ❌ Complete enumeration of valid `ReasonCode` values
- ❌ Explicit constraint that only listed codes are valid
- ❌ Warning against creating new reason codes

**Schema enforcement**:
- Validation occurs AFTER model generation
- Pydantic schema rejects invalid enums
- No pre-validation or guidance in prompt

### Why Model Created Invalid Enum

1. **No explicit enum list in prompt** - Model doesn't see all valid values
2. **Example shows pattern** - Shows 2 example codes, model infers pattern
3. **Semantic reasoning** - Model tries to express nuanced meaning
4. **No strict constraint warning** - Prompt doesn't emphasize enum strictness

---

## 7. COMPARISON: 10-CASE vs 100-CASE

| Metric | 10-case | 100-case |
|--------|---------|----------|
| Opportunities | 10 | 100 |
| Successful | 10 (100%) | 99 (99%) |
| Failed | 0 | 1 |
| Schema failures | 0 | 1 |
| Unique summaries | 10/10 | 99/99 |
| Diagnostic classes | 3 | 4 |
| Confidence unique | 2 | 6 |
| Mean latency | 16.1s | 13.2s |

**Observations**:
- ✅ Quality improved (more classes, more confidence variation)
- ✅ Latency improved (13.2s vs 16.1s)
- ⚠️ First schema failure appeared
- ✅ 99% success rate still excellent

---

## DECISION

### Recommended Action

**✅ B. KEEP CURRENT BEHAVIOR AND PROCEED TO 1,000**

### Rationale

1. **99% success rate is excellent**
   - 1% failure rate acceptable for offline batch processing
   - 990 successful diagnoses out of 1000 is sufficient for ML

2. **Schema failure is a known edge case**
   - Specific to one opportunity context
   - Deterministic model behavior (not random)
   - Well-understood root cause

3. **No systemic issue**
   - All other 99 opportunities succeeded
   - No pattern of failures
   - Model quality is good overall

4. **Retries are working as designed**
   - Schema failures trigger retries correctly
   - Issue is model determinism, not implementation

5. **Cost of fixing is high relative to benefit**
   - Would require prompt engineering (risky)
   - Or schema weakening (unacceptable)
   - Or post-processing normalization (complex)
   - Benefit: 1% improvement (marginal)

6. **Workaround is simple**
   - Document this as known limitation
   - Filter out failed diagnoses before ML training
   - 990/1000 is still excellent dataset

### Alternative Approaches (NOT Recommended)

#### A. Retry with structured-output recovery

**Approach**: Add prompt clarification or enum list on retry

**Pros**: Might recover this specific case

**Cons**:
- Adds complexity to retry logic
- Retries already failed (deterministic)
- Would need to modify prompt for retries only
- Risk of degrading other diagnoses

**Verdict**: ❌ Not worth complexity for 1% gain

#### C. Change local model

**Approach**: Try different Ollama model

**Pros**: Might have better enum adherence

**Cons**:
- Current model quality is good (99%)
- Unknown if other model would be better
- Would need to re-baseline
- Risk of worse performance overall

**Verdict**: ❌ Don't fix what isn't broken

#### D. Fix parser/implementation bug

**Approach**: Post-process to normalize enum

**Pros**: Could recover this specific case

**Cons**:
- This is NOT a parser bug (parser working correctly)
- Normalization would weaken schema validation
- "HIGHER_VALUE_PAYMENT" → "HIGH_VALUE_PAYMENT" is semantic change
- Would mask real failures in future

**Verdict**: ❌ Would compromise data quality

#### E. Weaken schema validation

**Approach**: Accept additional enum values

**Pros**: Would eliminate this failure

**Cons**:
- ❌ Schema is frozen per requirements
- ❌ Would allow model to invent unlimited enums
- ❌ Defeats purpose of constrained vocabulary
- ❌ ML features require stable enum set

**Verdict**: ❌ **ABSOLUTELY NOT** - violates frozen schema requirement

---

## 8. EXPECTED 1000-CASE BEHAVIOR

### Projected Failures

**Based on 100-case**: 1% schema failure rate

**Projected for 1000**:
- Expected successful: ~990
- Expected failed: ~10
- Schema failures: ~10
- LLM/API failures: 0

**Acceptable?**: Yes
- 990 successful diagnoses sufficient for ML
- Failure rate in normal range for LLM generation
- Better than Gemini (Stage A: 90%, Stage B: 4%)

### Risk Assessment

**Risk level**: LOW

**Known issues**:
- Model may generate creative enums for edge cases
- Deterministic failures (retry won't help)
- ~1% opportunities will fail

**Mitigation**:
- Document known failure mode
- Filter failed diagnoses before ML
- Monitor for new failure patterns

**Acceptable trade-offs**:
- 1% failure rate vs prompt complexity
- 990 diagnoses vs 1000 perfect diagnoses
- Simple implementation vs complex recovery logic

---

## 9. IMPLEMENTATION NOTES

### Current Retry Logic

**Correctly implemented**:
- ✅ Schema failures trigger retries
- ✅ Separate counters for schema vs API failures
- ✅ Error logging captures full details
- ✅ Max retries enforced (3 attempts)

**Limitation**:
- Retries use same prompt (deterministic output)
- No prompt variation or temperature increase
- Effective for transient issues, not model behavior

### Error Capture

**Working correctly**:
- ✅ ValidationError captured
- ✅ Full error message logged
- ✅ Retry number tracked
- ✅ Latency measured

### Schema Validation

**Working as designed**:
- ✅ Strict enum validation
- ✅ Rejects invalid values
- ✅ Clear error messages
- ✅ Frozen vocabulary enforced

---

## 10. RECOMMENDATION SUMMARY

### Proceed to 1000-case batch

**Command**:
```bash
source services/api/.venv/bin/activate
python ai/diagnosis/pilot_diagnose.py --provider local --limit 1000
```

**Expected**:
- Duration: ~3.7 hours
- Success: ~990 diagnoses
- Failures: ~10 schema errors
- Output: `datasets/v1.0.0/diagnoses_local/diagnoses_pilot_1000.parquet`

### After 1000-case completion

1. **Verify success rate** ≥ 98%
2. **Review failure patterns** (are they similar to opp_000026?)
3. **Filter failed diagnoses** before ML training
4. **Freeze diagnosis artifact** (version 1.1.0)
5. **Proceed to Model B feature engineering**

### Documentation

**Add to limitations**:
- Local model may generate creative enum values (~1% rate)
- Known edge case: "HIGHER_VALUE_PAYMENT" instead of "HIGH_VALUE_PAYMENT"
- Failed diagnoses excluded from ML training
- 99% success rate acceptable for offline batch processing

---

## 11. FILES FOR EVIDENCE

**Stage B artifacts** (100-case):
- `datasets/v1.0.0/diagnoses_local/diagnoses_pilot_100.parquet`
- `datasets/v1.0.0/diagnoses_local/error_log_pilot_100.json`
- `datasets/v1.0.0/diagnoses_local/manifest_pilot_100.json`
- `datasets/v1.0.0/diagnoses_local/confidence_report_pilot_100.txt`

**Preserved** for investigation

---

## 12. CONCLUSION

✅ **Stage B local diagnosis completed successfully with 99% success rate**

**Key findings**:
- 1 deterministic schema failure (invalid enum)
- Root cause: Model creativity vs strict constraints
- Retries triggered correctly but couldn't recover
- Overall quality excellent (unique summaries, good classes, stable latency)
- 99% success rate sufficient for ML training

**Recommendation**: **Proceed to 1,000-case batch**

**Confidence**: High

**Risk level**: Low

**Known limitation**: ~1% schema failures expected (acceptable)

---

**Investigation Complete**: 2026-08-26  
**Schema failures**: 1 opportunity (3 attempts)  
**Root cause**: Invalid enum "HIGHER_VALUE_PAYMENT"  
**Recommendation**: Keep current behavior, proceed to 1,000 ✅  
**Experimental integrity**: Preserved (no schema changes) ✅
