"""
Tests for confidence distribution analysis.

Verifies confidence reporting without claiming calibration.
"""

import pytest
import pandas as pd
import numpy as np
from ai.diagnosis.confidence_analysis import (
    analyze_confidence_distribution,
    format_confidence_report,
)


class TestAnalyzeConfidenceDistribution:
    """Test confidence distribution analysis."""

    def test_empty_dataframe(self):
        """Test with no successful diagnoses."""
        df = pd.DataFrame({
            'confidence': [],
            'diagnostic_status': [],
            'diagnostic_class': [],
        })

        result = analyze_confidence_distribution(df)

        assert result["total_successful"] == 0
        assert "error" in result

    def test_single_value(self):
        """Test with single confidence value repeated."""
        df = pd.DataFrame({
            'confidence': [0.95] * 10,
            'diagnostic_status': ['success'] * 10,
            'diagnostic_class': ['HARD_DECLINE'] * 10,
        })

        result = analyze_confidence_distribution(df)

        assert result["total_successful"] == 10
        assert result["unique_values"]["count"] == 1
        assert result["unique_values"]["values"] == [0.95]
        assert result["unique_values"]["frequencies"] == [10]

    def test_two_values(self):
        """Test with two distinct confidence values."""
        df = pd.DataFrame({
            'confidence': [0.85] * 3 + [0.95] * 7,
            'diagnostic_status': ['success'] * 10,
            'diagnostic_class': ['SOFT_DECLINE'] * 3 + ['HARD_DECLINE'] * 7,
        })

        result = analyze_confidence_distribution(df)

        assert result["total_successful"] == 10
        assert result["unique_values"]["count"] == 2
        assert result["unique_values"]["values"] == [0.85, 0.95]
        assert result["unique_values"]["frequencies"] == [3, 7]
        assert result["unique_values"]["percentages"] == [30.0, 70.0]

    def test_statistics_calculation(self):
        """Test confidence statistics calculation."""
        confidences = [0.70, 0.80, 0.85, 0.90, 0.95]
        df = pd.DataFrame({
            'confidence': confidences,
            'diagnostic_status': ['success'] * 5,
            'diagnostic_class': ['HARD_DECLINE'] * 5,
        })

        result = analyze_confidence_distribution(df)

        stats = result["confidence_statistics"]
        assert stats["min"] == 0.70
        assert stats["max"] == 0.95
        assert abs(stats["mean"] - np.mean(confidences)) < 0.001
        assert abs(stats["median"] - np.median(confidences)) < 0.001

    def test_distribution_by_class(self):
        """Test confidence distribution by diagnostic class."""
        df = pd.DataFrame({
            'confidence': [0.85, 0.90, 0.95, 0.95, 0.80],
            'diagnostic_status': ['success'] * 5,
            'diagnostic_class': [
                'SOFT_DECLINE', 'SOFT_DECLINE',
                'HARD_DECLINE', 'HARD_DECLINE', 'HARD_DECLINE'
            ],
        })

        result = analyze_confidence_distribution(df)

        by_class = result["distribution_by_class"]

        assert 'SOFT_DECLINE' in by_class
        assert by_class['SOFT_DECLINE']['count'] == 2
        assert abs(by_class['SOFT_DECLINE']['mean'] - 0.875) < 0.001

        assert 'HARD_DECLINE' in by_class
        assert by_class['HARD_DECLINE']['count'] == 3
        assert abs(by_class['HARD_DECLINE']['mean'] - 0.9) < 0.001

    def test_distribution_by_status(self):
        """Test confidence distribution including failed diagnoses."""
        df = pd.DataFrame({
            'confidence': [0.95, 0.90, 0.85, 0.0, 0.0],
            'diagnostic_status': [
                'success', 'success', 'success',
                'llm_failed', 'schema_failed'
            ],
            'diagnostic_class': [
                'HARD_DECLINE', 'SOFT_DECLINE', 'AUTHENTICATION_FAILURE',
                'UNKNOWN', 'UNKNOWN'
            ],
        })

        result = analyze_confidence_distribution(df)

        by_status = result["distribution_by_status"]

        assert 'success' in by_status
        assert by_status['success']['count'] == 3
        assert abs(by_status['success']['mean'] - 0.9) < 0.001

        assert 'llm_failed' in by_status
        assert by_status['llm_failed']['count'] == 1

    def test_histogram_generation(self):
        """Test histogram generation for larger datasets."""
        np.random.seed(42)
        confidences = np.random.uniform(0.7, 0.95, 50)

        df = pd.DataFrame({
            'confidence': confidences,
            'diagnostic_status': ['success'] * 50,
            'diagnostic_class': ['HARD_DECLINE'] * 50,
        })

        result = analyze_confidence_distribution(df)

        assert result["histogram"] is not None
        assert "counts" in result["histogram"]
        assert "bin_edges" in result["histogram"]
        assert len(result["histogram"]["counts"]) == 10

    def test_no_histogram_for_small_dataset(self):
        """Test that histogram not generated for < 10 samples."""
        df = pd.DataFrame({
            'confidence': [0.95] * 5,
            'diagnostic_status': ['success'] * 5,
            'diagnostic_class': ['HARD_DECLINE'] * 5,
        })

        result = analyze_confidence_distribution(df)

        assert result["histogram"] is None

    def test_filters_to_success_only(self):
        """Test that only successful diagnoses are analyzed."""
        df = pd.DataFrame({
            'confidence': [0.95, 0.90, 0.0, 0.0],
            'diagnostic_status': ['success', 'success', 'llm_failed', 'schema_failed'],
            'diagnostic_class': ['HARD_DECLINE', 'SOFT_DECLINE', 'UNKNOWN', 'UNKNOWN'],
        })

        result = analyze_confidence_distribution(df)

        assert result["total_successful"] == 2
        assert result["confidence_statistics"]["min"] == 0.90
        assert result["confidence_statistics"]["max"] == 0.95


class TestFormatConfidenceReport:
    """Test confidence report formatting."""

    def test_format_empty_result(self):
        """Test formatting when no successful diagnoses."""
        analysis = {
            "total_successful": 0,
            "error": "No successful diagnoses to analyze"
        }

        report = format_confidence_report(analysis)

        assert "Error:" in report
        assert "No successful diagnoses" in report

    def test_format_basic_report(self):
        """Test basic report formatting."""
        analysis = {
            "total_successful": 10,
            "confidence_statistics": {
                "min": 0.85,
                "max": 0.95,
                "mean": 0.92,
                "median": 0.95,
                "std": 0.04,
                "q25": 0.90,
                "q75": 0.95,
            },
            "unique_values": {
                "count": 2,
                "values": [0.85, 0.95],
                "frequencies": [2, 8],
                "percentages": [20.0, 80.0],
            },
            "distribution_by_class": {
                "HARD_DECLINE": {
                    "count": 6,
                    "mean": 0.93,
                    "median": 0.95,
                    "min": 0.85,
                    "max": 0.95,
                    "unique_values": 2,
                },
                "SOFT_DECLINE": {
                    "count": 4,
                    "mean": 0.90,
                    "median": 0.90,
                    "min": 0.85,
                    "max": 0.95,
                    "unique_values": 2,
                },
            },
            "distribution_by_status": {
                "success": {
                    "count": 10,
                    "mean": 0.92,
                    "median": 0.95,
                },
            },
        }

        report = format_confidence_report(analysis)

        # Verify key sections present
        assert "CONFIDENCE DISTRIBUTION ANALYSIS" in report
        assert "CONFIDENCE STATISTICS" in report
        assert "UNIQUE CONFIDENCE VALUES" in report
        assert "CONFIDENCE BY DIAGNOSTIC CLASS" in report
        assert "CONFIDENCE BY DIAGNOSTIC STATUS" in report

        # Verify statistics formatted
        assert "Min:    0.850" in report
        assert "Max:    0.950" in report
        assert "Mean:   0.920" in report

        # Verify unique values formatted
        assert "0.850: 2 occurrences (20.0%)" in report
        assert "0.950: 8 occurrences (80.0%)" in report

        # Verify disclaimer
        assert "descriptive only" in report.lower()
        assert "NOT validated for calibration" in report or "not validated for calibration" in report.lower()

    def test_warning_for_single_value(self):
        """Test warning when all confidence values identical."""
        analysis = {
            "total_successful": 10,
            "confidence_statistics": {
                "min": 0.95,
                "max": 0.95,
                "mean": 0.95,
                "median": 0.95,
                "std": 0.0,
                "q25": 0.95,
                "q75": 0.95,
            },
            "unique_values": {
                "count": 1,
                "values": [0.95],
                "frequencies": [10],
                "percentages": [100.0],
            },
            "distribution_by_class": {},
            "distribution_by_status": {},
        }

        report = format_confidence_report(analysis)

        assert "WARNING" in report
        assert "All confidence values identical" in report

    def test_warning_for_two_values(self):
        """Test note for only 2 unique values."""
        analysis = {
            "total_successful": 9,
            "confidence_statistics": {
                "min": 0.85,
                "max": 0.95,
                "mean": 0.939,
                "median": 0.95,
                "std": 0.033,
                "q25": 0.95,
                "q75": 0.95,
            },
            "unique_values": {
                "count": 2,
                "values": [0.85, 0.95],
                "frequencies": [1, 8],
                "percentages": [11.1, 88.9],
            },
            "distribution_by_class": {},
            "distribution_by_status": {},
        }

        report = format_confidence_report(analysis)

        assert "NOTE: Only 2 unique confidence values" in report


class TestConfidenceAnalysisIntegration:
    """Integration tests for confidence analysis."""

    def test_stage_a_pilot_data(self):
        """Test with realistic Stage A pilot data."""
        # Simulating Stage A results: 9 success, 1 failed
        df = pd.DataFrame({
            'confidence': [0.95, 0.95, 0.95, 0.95, 0.95, 0.85, 0.95, 0.95, 0.95, 0.0],
            'diagnostic_status': ['success'] * 9 + ['llm_failed'],
            'diagnostic_class': [
                'AUTHENTICATION_FAILURE', 'SOFT_DECLINE', 'HARD_DECLINE',
                'HARD_DECLINE', 'HARD_DECLINE', 'SOFT_DECLINE',
                'HARD_DECLINE', 'AUTHENTICATION_FAILURE', 'HARD_DECLINE',
                'UNKNOWN'
            ],
        })

        result = analyze_confidence_distribution(df)

        # Verify analysis matches Stage A patterns
        assert result["total_successful"] == 9
        assert result["unique_values"]["count"] == 2
        assert result["confidence_statistics"]["mean"] > 0.93
        assert result["confidence_statistics"]["median"] == 0.95

        # Verify report can be generated
        report = format_confidence_report(result)
        assert "Only 2 unique confidence values" in report
        assert "discrete confidence levels" in report.lower()
