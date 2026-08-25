# RAY V1 Offline LLM Diagnostic Enrichment Report

## Overview

This document describes the offline LLM diagnostic enrichment layer for RAY V1.

**CRITICAL**: The LLM diagnosis is **diagnostic enrichment**, NOT ground truth. It does NOT replace the canonical observable `failure_class` from the simulator.

## Version Information

- **Diagnosis Version**: 1.0.0
- **Prompt Version**: 1.0.0
- **Schema Version**: 1.0.0
- **Status**: **FROZEN** (for evaluation reproducibility)

## Purpose

The LLM transforms raw observable payment failure context into structured diagnostic evidence that:

1. Enriches the failure classification with additional reasoning
2. Provides human-readable diagnostic summaries
3. Extracts structured reason codes from failure descriptions
4. Assigns confidence scores to diagnostic assessments

## Architectural Principles

### 1. Enrichment, Not Replacement

The LLM does NOT overwrite the canonical `failure_class` from the simulator.

Instead, it provides a parallel `diagnostic_class` with supporting evidence.

### 2. Observable Information Only

The LLM receives ONLY information available at decision time:

**Allowed Inputs**:
- Payment amount, method, currency
- Canonical failure class
- Failure description
- Customer historical payment metrics
- Customer historical recovery metrics
- Payment amount context (relative to customer average)

**Forbidden Inputs**:
- True organic recovery probability
- True payment link recovery probability
- Customer latent traits (hidden)
- Scenario ID (hidden)
- Future outcomes
- Ground truth labels

### 3. Offline Processing Only

Diagnosis is run **ONCE** in batch mode and cached.

The evaluation benchmark uses **cached results only**.

**There are ZERO live LLM calls during final benchmark execution.**

### 4. No Action Selection

The LLM does NOT recommend actions. It only provides diagnostic classification and reasoning.

## Output Schema

### Structured Output

```json
{
  "diagnostic_class": "SOFT_DECLINE",
  "reason_codes": ["TEMPORARY_FAILURE", "STRONG_PAYMENT_HISTORY"],
  "diagnostic_summary": "Human-readable explanation",
  "confidence": 0.85
}
```

### Diagnostic Classes

- `SOFT_DECLINE`: Temporary, potentially recoverable failures
- `HARD_DECLINE`: Persistent, structural failures
- `AUTHENTICATION_FAILURE`: Authentication/verification issues
- `GATEWAY_ERROR`: Technical/system failures
- `UNKNOWN`: Insufficient information

### Reason Code Vocabulary

**Failure Characteristics**:
- `ISSUER_DECLINE`: Declined by issuing bank
- `TEMPORARY_FAILURE`: Likely temporary/transient
- `LIKELY_TRANSIENT`: Could resolve naturally
- `PERSISTENT_FAILURE`: Structural/permanent issue
- `AUTHENTICATION_ISSUE`: Auth/verification problem
- `GATEWAY_ISSUE`: Technical system issue

**Customer Context**:
- `STRONG_PAYMENT_HISTORY`: Good payment track record
- `WEAK_PAYMENT_HISTORY`: Poor payment track record
- `RECENT_FAILURE_PATTERN`: Recent pattern of failures
- `HIGH_RECOVERY_HISTORY`: Often recovers from failures
- `LOW_RECOVERY_HISTORY`: Rarely recovers from failures

**Payment Context**:
- `HIGH_VALUE_PAYMENT`: Significantly higher than average
- `LOW_VALUE_PAYMENT`: Significantly lower than average
- `PAYMENT_METHOD_SIGNAL`: Payment method relevant

**Diagnostic Quality**:
- `LOW_CONTEXT_CONFIDENCE`: Limited context
- `INSUFFICIENT_INFORMATION`: Not enough information

### Confidence Scoring

- **0.9-1.0**: Strong evidence, clear classification
- **0.7-0.9**: Good evidence, reasonable confidence
- **0.5-0.7**: Moderate evidence, some uncertainty
- **0.3-0.5**: Weak evidence, significant uncertainty
- **0.0-0.3**: Very weak evidence, low confidence

**Threshold**: 0.70 (configured)

Diagnoses with confidence < 0.70 are marked `LOW_CONFIDENCE`.

## Processing Pipeline

### 1. Batch Processing

All 1,000 opportunities processed in batch:

```bash
python ai/diagnosis/batch_diagnose.py \
  --dataset datasets/v1.0.0 \
  --output datasets/v1.0.0/diagnoses \
  --provider anthropic \
  --model claude-3-5-sonnet-20241022
```

### 2. Retry Logic

- **Max retries**: 3 per opportunity
- **Backoff**: 0.5s, 1.0s, 1.5s between attempts
- **Failure modes**:
  - Schema validation failure
  - LLM API call failure
  - Persistent failures → `SAFE_HALT` status

### 3. Caching

Results cached to:
```
datasets/v1.0.0/diagnoses/
├── diagnoses.parquet
└── diagnosis_manifest.json
```

### 4. Quality Analysis

Quality analyzed with:

```bash
python ai/diagnosis/analyze_quality.py \
  --dataset datasets/v1.0.0 \
  --diagnoses datasets/v1.0.0/diagnoses
```

## Dry Run Results

The dry-run test (mock LLM responses) produced:

- **Total opportunities**: 1,000
- **Successful diagnoses**: 1,000
- **Low confidence**: 0
- **Schema failures**: 0
- **LLM failures**: 0
- **Success rate**: 100%

**Note**: Dry run uses mock responses for testing. Actual LLM diagnosis would produce realistic variation.

## ML Ablation Preparation

Two feature sets prepared for ML comparison (Prompt 3):

### Model A: Observable Only

- Payment details
- Customer history metrics
- Canonical failure class
- NO LLM diagnostic features

### Model B: Observable + LLM Enrichment

- All Model A features
- LLM diagnostic class
- LLM reason codes
- LLM confidence
- Diagnostic status

**Purpose**: Determine if LLM enrichment provides measurable improvement to ML recovery prediction.

## Canonical vs LLM Comparison

The analysis compares:
- Canonical `failure_class` (from simulator)
- LLM `diagnostic_class` (enrichment)

**This comparison is for diagnostics only.**

Disagreement does NOT mean the LLM is "wrong" - it represents:
1. Different interpretation of ambiguous signals
2. Additional context from customer history
3. Diagnostic perspective vs classification

Sample disagreements are inspected to understand LLM reasoning.

## Schema Validation

Strict validation enforces:

✓ Diagnostic class in allowed vocabulary  
✓ At least one reason code  
✓ No duplicate reason codes  
✓ Reason codes in constrained vocabulary  
✓ Confidence in [0.0, 1.0]  
✓ Summary length 10-500 characters  

Invalid output triggers retry with formatting instructions.

## Failure Handling

### Schema Validation Failure
- Record failure
- Retry with explicit formatting instructions
- After max retries: `SAFE_HALT` with `UNKNOWN` class

### LLM API Call Failure
- Record failure
- Exponential backoff retry
- After max retries: `SAFE_HALT` with `UNKNOWN` class

### Safe Halt Record
```json
{
  "diagnostic_class": "UNKNOWN",
  "reason_codes": ["INSUFFICIENT_INFORMATION"],
  "diagnostic_summary": "Diagnosis failed: [status]",
  "confidence": 0.0,
  "diagnostic_status": "SAFE_HALT"
}
```

## Reproducibility

### Version Tracking

Every diagnosis record includes:
- `diagnosis_version`: 1.0.0
- `diagnosis_prompt_version`: 1.0.0
- `diagnosis_model_version`: claude-3-5-sonnet-20241022
- `diagnosis_schema_version`: 1.0.0
- `generation_timestamp`: ISO 8601 timestamp

### Deterministic Caching

Once generated, diagnosis results are **FROZEN**.

The benchmark loads cached artifacts only.

To regenerate (invalidates prior results):
1. Increment `diagnosis_version`
2. Document reason in `docs/decisions.md`
3. Re-run batch diagnosis
4. Re-run downstream ML training
5. Re-run evaluation

## Known Limitations

### 1. Synthetic Data Only

Diagnosis performed on synthetic failure descriptions.

Real-world failure descriptions may differ in:
- Language/terminology
- Ambiguity levels
- Context richness

### 2. Single Model

V1 uses one LLM model (claude-3-5-sonnet-20241022).

Multi-model ensemble not explored.

### 3. Static Prompt

Prompt is frozen at v1.0.0.

Prompt engineering improvements require new diagnosis version.

### 4. No Contextual Learning

Each diagnosis is independent.

No learning from batch patterns or feedback.

### 5. Binary Confidence Threshold

Single threshold (0.70) for confidence.

No graduated confidence handling.

## Testing

Comprehensive test coverage:

✓ Diagnostic class enum validation  
✓ Reason code vocabulary constraints  
✓ Schema validation (confidence range, summary length)  
✓ Duplicate reason code rejection  
✓ Observable-only input verification  
✓ Version tracking  
✓ Cache formatting  

**Test results**: 11/11 passing

## Usage in Downstream Prompts

### Prompt 3: ML Model Training

ML models will compare:
- Model A: Without LLM features
- Model B: With LLM features

Performance delta determines LLM value.

### Prompt 4+: Production Pipeline

If LLM features prove valuable:
- Load cached diagnosis during training
- Use diagnosis features in ML inference
- Include diagnostic summary in human explanations

If LLM features do NOT improve performance:
- Exclude from production ML model
- Optionally use for human explanation only

## Files Created

**Core components**:
- `ai/diagnosis/schema.py`: Pydantic schemas and validation
- `ai/diagnosis/prompt.py`: LLM prompt template
- `ai/diagnosis/batch_diagnose.py`: Batch processing script
- `ai/diagnosis/analyze_quality.py`: Quality analysis script

**Tests**:
- `tests/unit/test_diagnosis.py`: Schema and prompt tests (11 tests)

**Documentation**:
- `docs/diagnosis-v1.0-report.md`: This document

## Next Steps

This diagnosis enrichment is ready for:

1. **Actual LLM Processing** (if API keys available):
   ```bash
   export LLM_API_KEY=<your-key>
   python ai/diagnosis/batch_diagnose.py
   ```

2. **Prompt 3**: ML model training with ablation study (with/without LLM features)

3. **Feature Engineering**: Convert diagnosis artifacts into ML features

**Diagnosis layer is FROZEN and ready for ML training.**

---

*Diagnosis version: 1.0.0*  
*Prompt version: 1.0.0*  
*Schema version: 1.0.0*  
*Status: FROZEN*
