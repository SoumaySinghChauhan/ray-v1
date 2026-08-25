# Gemini Model Update — gemini-3.6-flash

## Summary

Updated RAY Gemini provider from deprecated `gemini-2.5-flash` to current `gemini-3.6-flash`.

## Changes Made

### 1. Batch Diagnosis Provider
**File**: `ai/diagnosis/batch_diagnose.py:86`

```python
# Before
elif llm_provider == "gemini":
    self.model = "gemini-2.5-flash"

# After  
elif llm_provider == "gemini":
    self.model = "gemini-3.6-flash"
```

### 2. Smoke Test
**File**: `ai/diagnosis/smoke_test.py:52`

```python
# Before
model_name = "gemini-2.5-flash"

# After
model_name = "gemini-3.6-flash"
```

### 3. Authentication Debug Tool
**File**: `ai/diagnosis/auth_debug.py:68`

```python
# Before
model = "gemini-2.5-flash"

# After
model = "gemini-3.6-flash"
```

### 4. Documentation Updates
- Updated `docs/prompt3-completion-status.md` with model change
- Updated `README.md` with Gemini provider example

## Configuration

**Configured Model**: `gemini-3.6-flash`  
**Provider**: `gemini`  
**SDK**: `google-genai` (current official Python SDK)

## Verification Steps

### Step 1: Run Smoke Test (ONE Request)

```bash
# Set your working Gemini API key
export GEMINI_API_KEY="your_working_key"

# Activate Python environment
cd services/api
source .venv/bin/activate

# Run smoke test
cd ../..
python ai/diagnosis/smoke_test.py --provider gemini
```

**Expected Output** (if working):
```
======================================================================
GEMINI DIAGNOSIS SMOKE TEST
======================================================================

API Key: AIzaSy****...****
✓ Client initialized with model: gemini-3.6-flash
✓ Test prompt created
✓ API call successful
✓ Valid JSON received
✓ Schema validation passed
✓ No secrets detected in output

======================================================================
✅ SMOKE TEST PASSED
======================================================================
```

**If smoke test passes**, proceed to Step 2.

### Step 2: Run Full Batch Diagnosis (1,000 Opportunities)

```bash
# With working API key set
python ai/diagnosis/batch_diagnose.py \
  --provider gemini \
  --output datasets/v1.0.0/diagnoses_real
```

**Expected**:
- Duration: 30-60 minutes
- Cost: ~$5-15
- Output: 1,000 real diagnoses with variation

### Step 3: Verify Diagnosis Quality

```bash
python ai/diagnosis/analyze_quality.py \
  --diagnoses datasets/v1.0.0/diagnoses_real
```

**Should show**:
- Unique summaries: >> 100 (not all identical)
- Unique classes: 3-5 different diagnostic classes
- Unique confidence values: >> 10
- Real timing variation (not constant 63ms)

## What Remains Unchanged

✅ Diagnosis schema (Pydantic models)  
✅ Prompt templates and system prompt  
✅ Dataset (frozen v1.0.0)  
✅ Simulator  
✅ ML architecture  
✅ Feature definitions  
✅ Baseline  
✅ Test set firewall (300 customers untouched)

## Next Steps After Smoke Test Passes

1. **Run full batch diagnosis** (30-60 min, $5-15)
2. **Verify realistic variation** in diagnoses
3. **Freeze diagnosis v1.0.1**
4. **Regenerate Model B features** with real LLM diagnosis
5. **Implement ML training script** (if not done)
6. **Train Model A** (observable features only)
7. **Train Model B** (observable + LLM features)
8. **Compare models on validation set**
9. **Generate validation report**

## Files Modified

```
ai/diagnosis/batch_diagnose.py      # Line 86: gemini-3.6-flash
ai/diagnosis/smoke_test.py          # Line 52: gemini-3.6-flash  
ai/diagnosis/auth_debug.py          # Line 68: gemini-3.6-flash
docs/prompt3-completion-status.md   # Updated status
README.md                            # Updated Gemini example
```

## Status

**Model**: ✅ Updated to `gemini-3.6-flash`  
**Authentication**: ✅ Working (per user confirmation)  
**Smoke Test**: ⏸️ Awaiting user execution  
**Full Diagnosis**: ⏸️ Awaiting smoke test pass

---

**Updated**: 2026-08-25  
**Model Version**: `gemini-3.6-flash`  
**Change Reason**: `gemini-2.5-flash` deprecated (404 NOT_FOUND)
