"""
Confidence distribution analysis for diagnosis quality assessment.

Does NOT claim calibration - purely descriptive statistics.
"""

import pandas as pd
import numpy as np
from typing import Any


def analyze_confidence_distribution(df: pd.DataFrame) -> dict[str, Any]:
    """
    Analyze confidence value distribution in diagnosis results.

    Args:
        df: DataFrame with 'confidence' and 'diagnostic_class' columns

    Returns:
        Dictionary with confidence analysis
    """
    # Filter to successful diagnoses only
    success_df = df[df['diagnostic_status'] == 'success'].copy()

    if len(success_df) == 0:
        return {
            "total_successful": 0,
            "error": "No successful diagnoses to analyze"
        }

    analysis = {
        "total_successful": len(success_df),
        "confidence_statistics": {},
        "unique_values": {},
        "distribution_by_class": {},
        "distribution_by_status": {},
    }

    # Basic statistics
    confidences = success_df['confidence']
    analysis["confidence_statistics"] = {
        "min": float(confidences.min()),
        "max": float(confidences.max()),
        "mean": float(confidences.mean()),
        "median": float(confidences.median()),
        "std": float(confidences.std()),
        "q25": float(confidences.quantile(0.25)),
        "q75": float(confidences.quantile(0.75)),
    }

    # Unique values and frequency
    value_counts = confidences.value_counts().sort_index()
    analysis["unique_values"] = {
        "count": len(value_counts),
        "values": [float(v) for v in value_counts.index.tolist()],
        "frequencies": value_counts.tolist(),
        "percentages": (value_counts / len(success_df) * 100).tolist(),
    }

    # Histogram bins
    if len(success_df) >= 10:
        hist, bin_edges = np.histogram(confidences, bins=10)
        analysis["histogram"] = {
            "counts": hist.tolist(),
            "bin_edges": bin_edges.tolist(),
        }
    else:
        analysis["histogram"] = None

    # Confidence by diagnostic class
    if 'diagnostic_class' in success_df.columns:
        by_class = {}
        for cls in success_df['diagnostic_class'].unique():
            class_df = success_df[success_df['diagnostic_class'] == cls]
            class_conf = class_df['confidence']
            by_class[cls] = {
                "count": len(class_df),
                "mean": float(class_conf.mean()),
                "median": float(class_conf.median()),
                "min": float(class_conf.min()),
                "max": float(class_conf.max()),
                "unique_values": len(class_conf.unique()),
            }
        analysis["distribution_by_class"] = by_class

    # Confidence by final status (include failed)
    by_status = {}
    for status in df['diagnostic_status'].unique():
        status_df = df[df['diagnostic_status'] == status]
        status_conf = status_df['confidence']
        by_status[status] = {
            "count": len(status_df),
            "mean": float(status_conf.mean()) if len(status_df) > 0 else None,
            "median": float(status_conf.median()) if len(status_df) > 0 else None,
        }
    analysis["distribution_by_status"] = by_status

    return analysis


def format_confidence_report(analysis: dict[str, Any]) -> str:
    """
    Format confidence analysis as readable report.

    Args:
        analysis: Result from analyze_confidence_distribution()

    Returns:
        Formatted report string
    """
    if "error" in analysis:
        return f"Error: {analysis['error']}"

    lines = []
    lines.append("=" * 70)
    lines.append("CONFIDENCE DISTRIBUTION ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    # Basic stats
    stats = analysis["confidence_statistics"]
    lines.append("1. CONFIDENCE STATISTICS")
    lines.append(f"   Min:    {stats['min']:.3f}")
    lines.append(f"   Q25:    {stats['q25']:.3f}")
    lines.append(f"   Median: {stats['median']:.3f}")
    lines.append(f"   Mean:   {stats['mean']:.3f}")
    lines.append(f"   Q75:    {stats['q75']:.3f}")
    lines.append(f"   Max:    {stats['max']:.3f}")
    lines.append(f"   Std:    {stats['std']:.3f}")
    lines.append("")

    # Unique values
    unique = analysis["unique_values"]
    lines.append("2. UNIQUE CONFIDENCE VALUES")
    lines.append(f"   Count: {unique['count']}")
    lines.append("")
    lines.append("   Value Frequency:")
    for val, freq, pct in zip(unique['values'], unique['frequencies'], unique['percentages']):
        lines.append(f"     {val:.3f}: {freq} occurrences ({pct:.1f}%)")
    lines.append("")

    # Interpretation
    if unique['count'] == 1:
        lines.append("   ⚠️  WARNING: All confidence values identical")
        lines.append("   This suggests LLM may not be varying confidence appropriately")
    elif unique['count'] == 2:
        lines.append("   ⚠️  NOTE: Only 2 unique confidence values")
        lines.append("   LLM may be using discrete confidence levels (e.g., high/low)")
    elif unique['count'] <= 5:
        lines.append("   ✓ Limited variation (discrete levels)")
    else:
        lines.append("   ✓ Good variation in confidence values")
    lines.append("")

    # By diagnostic class
    if analysis["distribution_by_class"]:
        lines.append("3. CONFIDENCE BY DIAGNOSTIC CLASS")
        for cls, stats in sorted(analysis["distribution_by_class"].items()):
            lines.append(f"   {cls}:")
            lines.append(f"     Count: {stats['count']}")
            lines.append(f"     Mean: {stats['mean']:.3f}")
            lines.append(f"     Range: [{stats['min']:.3f}, {stats['max']:.3f}]")
            lines.append(f"     Unique values: {stats['unique_values']}")
        lines.append("")

    # By status
    if analysis["distribution_by_status"]:
        lines.append("4. CONFIDENCE BY DIAGNOSTIC STATUS")
        for status, stats in sorted(analysis["distribution_by_status"].items()):
            lines.append(f"   {status}:")
            lines.append(f"     Count: {stats['count']}")
            if stats['mean'] is not None:
                lines.append(f"     Mean: {stats['mean']:.3f}")
            else:
                lines.append(f"     Mean: N/A (no confidence for failed)")
        lines.append("")

    # Disclaimer
    lines.append("NOTE: This analysis is descriptive only.")
    lines.append("Confidence values are NOT validated for calibration.")
    lines.append("High/low confidence does not guarantee accuracy.")
    lines.append("")

    return "\n".join(lines)
