"""
Tests for safe error capture in LLM diagnosis.

Verifies that API errors are captured without exposing secrets.
"""

import pytest
from ai.diagnosis.error_capture import (
    sanitize_error_message,
    capture_api_error,
    verify_no_secrets,
)


class TestSanitizeErrorMessage:
    """Test error message sanitization."""

    def test_sanitize_api_key_basic(self):
        """Test that API key is redacted from error message."""
        api_key = "AIzaSyBBN6IK1ef_uDSDr_VNKJ7KM5GmyZwYX8Z-R093AJyC6Rhrag"
        message = f"API error: Invalid key {api_key}"

        sanitized = sanitize_error_message(message, api_key)

        assert api_key not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_sanitize_bearer_token(self):
        """Test that Bearer tokens are redacted."""
        message = "Authorization: Bearer abc123xyz456"

        sanitized = sanitize_error_message(message)

        assert "abc123xyz456" not in sanitized
        assert "Bearer [REDACTED]" in sanitized

    def test_sanitize_sk_pattern(self):
        """Test that sk- patterns (Anthropic/OpenAI) are redacted."""
        message = "Using key sk-ant-api03-abcdefg123456789"

        sanitized = sanitize_error_message(message)

        assert "sk-ant-api03-abcdefg123456789" not in sanitized
        assert "sk-[REDACTED]" in sanitized

    def test_sanitize_aiza_pattern(self):
        """Test that AIza patterns (Google) are redacted."""
        message = "Invalid key: AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"

        sanitized = sanitize_error_message(message)

        assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ123456789" not in sanitized
        assert "AIza[REDACTED]" in sanitized

    def test_no_sanitization_needed(self):
        """Test that clean messages pass through unchanged."""
        message = "Request timed out after 30 seconds"

        sanitized = sanitize_error_message(message)

        assert sanitized == message


class TestCaptureApiError:
    """Test API error capture."""

    def test_capture_basic_exception(self):
        """Test capturing a basic exception."""
        exc = ValueError("Something went wrong")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_001",
            retry_number=0,
        )

        assert record["opportunity_id"] == "opp_001"
        assert record["retry_number"] == 0
        assert record["exception_type"] == "ValueError"
        assert "Something went wrong" in record["error_message"]
        assert "timestamp" in record

    def test_capture_with_api_key_redaction(self):
        """Test that API key in exception is redacted."""
        api_key = "AIzaSyTESTKEY123456789"
        exc = Exception(f"Invalid API key: {api_key}")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_002",
            retry_number=1,
            api_key=api_key,
        )

        assert api_key not in record["error_message"]
        assert "[REDACTED_API_KEY]" in record["error_message"]

    def test_extract_http_status(self):
        """Test HTTP status extraction from error message."""
        exc = Exception("400 INVALID_ARGUMENT: Bad request")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_003",
            retry_number=0,
        )

        assert record["http_status"] == 400

    def test_detect_rate_limit_error(self):
        """Test rate limit error detection."""
        exc = Exception("RATE_LIMIT_EXCEEDED: Too many requests")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_004",
            retry_number=2,
        )

        assert record["error_reason"] == "RATE_LIMIT_EXCEEDED"
        assert record["failure_category"] == "transient"

    def test_detect_api_key_invalid(self):
        """Test API key invalid error detection."""
        exc = Exception("API_KEY_INVALID: Please pass a valid API key")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_005",
            retry_number=0,
        )

        assert record["error_reason"] == "API_KEY_INVALID"
        assert record["failure_category"] == "permanent"

    def test_detect_timeout(self):
        """Test timeout error detection."""
        exc = Exception("Request timeout after 60 seconds")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_006",
            retry_number=1,
        )

        assert record["error_reason"] == "TIMEOUT"
        assert record["failure_category"] == "transient"

    def test_detect_content_filter(self):
        """Test content filter detection."""
        exc = Exception("CONTENT_FILTER: Request blocked by safety filter")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_007",
            retry_number=0,
        )

        assert record["error_reason"] == "CONTENT_FILTER"
        assert record["failure_category"] == "request_specific"

    def test_capture_with_latency(self):
        """Test latency capture."""
        exc = Exception("Service unavailable")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_008",
            retry_number=0,
            latency_ms=15432.5,
        )

        assert record["latency_ms"] == 15432.5

    def test_unknown_error_category(self):
        """Test unknown error gets 'unknown' category."""
        exc = Exception("Some mysterious error")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_009",
            retry_number=0,
        )

        assert record["failure_category"] == "unknown"

    def test_error_message_truncation(self):
        """Test that very long error messages are truncated."""
        long_message = "Error: " + "x" * 1000
        exc = Exception(long_message)

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_010",
            retry_number=0,
        )

        assert len(record["error_message"]) <= 500


class TestVerifyNoSecrets:
    """Test secret detection."""

    def test_no_secrets_clean_text(self):
        """Test that clean text passes."""
        text = "This is a normal error message"
        secrets = ["secret_key_123", "password456"]

        assert verify_no_secrets(text, secrets) is True

    def test_detect_secret_present(self):
        """Test that secrets are detected."""
        text = "Error with key: secret_key_123"
        secrets = ["secret_key_123"]

        assert verify_no_secrets(text, secrets) is False

    def test_empty_secret_ignored(self):
        """Test that empty/None secrets are ignored."""
        text = "Normal text"
        secrets = ["", None, "actual_secret"]

        # Should pass since actual_secret not in text
        assert verify_no_secrets(text, secrets) is True

    def test_multiple_secrets(self):
        """Test detection of multiple secrets."""
        text = "Using password456 for authentication"
        secrets = ["secret_key_123", "password456", "token789"]

        assert verify_no_secrets(text, secrets) is False


class TestErrorCaptureIntegration:
    """Integration tests for error capture."""

    def test_complete_error_capture_flow(self):
        """Test complete error capture with all features."""
        api_key = "AIzaSyINTEGRATIONTEST123"
        exc = Exception(f"400 API_KEY_INVALID: Key {api_key} is not valid")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_integration_001",
            retry_number=2,
            api_key=api_key,
            latency_ms=5432.1,
        )

        # Verify all fields present
        assert record["opportunity_id"] == "opp_integration_001"
        assert record["retry_number"] == 2
        assert record["exception_type"] == "Exception"
        assert record["latency_ms"] == 5432.1
        assert record["timestamp"] is not None

        # Verify API key redacted
        assert api_key not in record["error_message"]
        assert "[REDACTED_API_KEY]" in record["error_message"]

        # Verify error categorization
        assert record["error_reason"] == "API_KEY_INVALID"
        assert record["failure_category"] == "permanent"
        assert record["http_status"] == 400

        # Verify the complete record can be serialized (no datetime objects)
        import json
        serialized = json.dumps(record)
        assert isinstance(serialized, str)

    def test_no_api_key_provided(self):
        """Test error capture when API key not provided."""
        exc = Exception("Generic error")

        record = capture_api_error(
            exception=exc,
            opportunity_id="opp_nokey",
            retry_number=0,
            api_key=None,
        )

        # Should not crash
        assert record["exception_type"] == "Exception"
        assert "Generic error" in record["error_message"]
