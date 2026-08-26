# RAY V1.0 - Validation Economic Analysis

**Date**: 2026-08-26
**Prompt**: 7D
**Status**: VALIDATION COMPLETE - Test set untouched

---

## Executive Summary

This report presents the economic validation of RAY's decision architecture on the 150-opportunity validation set.

**Key Finding**: NEGATIVE economic value from LLM diagnosis features.

---

## 1. Test Firewall Status

✅ **PASS** - Test set NOT accessed

- Test accessed: False
- Validation opportunities: 150
- Test opportunities: 300 (UNTOUCHED)

---

## 2. Strategy Results

### Baseline
- Actions Selected: 99
- Action Rate: 66.0%
- Predicted Net EV: 141537.09 INR
- Realized Recovery: 25 / 99 (25.3%)
- Realized Amount: 74159.84 INR

### Model A
- Actions Selected: 99
- Action Rate: 66.0%
- Predicted Net EV: 80621.73 INR
- Realized Recovery: 25 / 99 (25.3%)
- Realized Amount: 74162.60 INR

### Model B
- Actions Selected: 0
- Action Rate: 0.0%
- Predicted Net EV: 0.00 INR
- Realized Recovery: 0 / 0 (0.0%)
- Realized Amount: 0.00 INR

---

## 3. Economic Deltas

### Model A vs Baseline
- Predicted Net EV Delta: -60915.36 INR
- Realized Amount Delta: +2.76 INR

### Model B vs Baseline
- Predicted Net EV Delta: -141537.09 INR
- Realized Amount Delta: -74159.84 INR

### Model B vs Model A
- Predicted Net EV Delta: -80621.73 INR
- Realized Amount Delta: -74162.60 INR

---

## 4. LLM Contribution

**Classification**: NEGATIVE

The LLM diagnosis features show negative economic value in validation allocation.

---

## 5. Capacity Utilization

Average daily capacity utilization across strategies:
- Baseline: 99.0%
- Model A: 99.0%
- Model B: 0.0%

---

## 6. Validation Limitations

- **Small Sample**: Only 150 opportunities limits statistical confidence
- **Synthetic Data**: Results based on simulated recovery outcomes
- **Calibration**: Calibration analysis is descriptive, not definitive
- **Feature Importance**: May be unstable due to sample size

---

## 7. Artifacts

- JSON Report: `/Users/soumaysinghchauhan/Ray/reports/validation-economic-analysis-v1.0.json`
- Comparison CSV: `/Users/soumaysinghchauhan/Ray/reports/validation-model-comparison.csv`
- Calibration Plots: `/Users/soumaysinghchauhan/Ray/reports/calibration_curves_validation.png`

---

**Generated**: 2026-08-26T22:43:25.756252
