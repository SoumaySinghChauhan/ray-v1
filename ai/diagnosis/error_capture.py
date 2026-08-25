"""
Safe error capture for LLM diagnosis failures.

Captures diagnostic metadata without exposing secrets.
"""

import re
from datetime import datetime, timezone
from typing import Any


def sanitize_error_message(message: str, api_key: str | None = None) -> str:
    """
    Remove secrets from error messages.

    Args:
        message: Raw error message
        api_key: API key to redact if present

    Returns:
        Sanitized error message
    """
    if api_key and api_key in message:
        message = message.replace(api_key, "[REDACTED_API_KEY]")

    # Redact common secret patterns
    patterns = [
        (r'Bearer [A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-._~+/]+=*', 'api_key=[REDACTED]'),
        (r'sk-[A-Za-z0-9\-]{20,}', 'sk-[REDACTED]'),
        (r'AIza[A-Za-z0-9\-_]{35,}', 'AIza[REDACTED]'),
    ]

    for pattern, replacement in patterns:
        message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

    return message


def capture_api_error(
    exception: Exception,
    opportunity_id: str,
    retry_number: int,
    api_key: str | None = None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    """
    Capture safe diagnostic metadata from API failure.

    Does NOT log:
    - API keys
    - Authorization headers
    - Secrets
    - Full request payloads

    Args:
        exception: The exception that occurred
        opportunity_id: Opportunity being processed
        retry_number: Which retry attempt (0 = initial)
        api_key: API key (used only for redaction)
        latency_ms: Request latency if available

    Returns:
        Safe error metadata dictionary
    """
    error_record = {
        "opportunity_id": opportunity_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_number": retry_number,
        "exception_type": type(exception).__name__,
        "latency_ms": latency_ms,
    }

    # Sanitize error message
    raw_message = str(exception)
    safe_message = sanitize_error_message(raw_message, api_key)
    error_record["error_message"] = safe_message[:500]  # Truncate to prevent log explosion

    # Extract HTTP status if available
    if hasattr(exception, 'status_code'):
        error_record["http_status"] = exception.status_code
    elif hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        error_record["http_status"] = exception.response.status_code
    else:
        # Try to parse from message
        import re
        status_match = re.search(r'\b(4\d{2}|5\d{2})\b', raw_message)
        if status_match:
            error_record["http_status"] = int(status_match.group(1))
        else:
            error_record["http_status"] = None

    # Extract API error code/reason if available
    error_code = None
    error_reason = None

    # Common patterns
    if 'API_KEY_INVALID' in raw_message:
        error_reason = 'API_KEY_INVALID'
    elif 'RATE_LIMIT' in raw_message or 'rate limit' in raw_message.lower():
        error_reason = 'RATE_LIMIT_EXCEEDED'
    elif 'TIMEOUT' in raw_message or 'timeout' in raw_message.lower():
        error_reason = 'TIMEOUT'
    elif 'CONTENT_FILTER' in raw_message or 'safety' in raw_message.lower():
        error_reason = 'CONTENT_FILTER'
    elif 'INVALID_ARGUMENT' in raw_message:
        error_reason = 'INVALID_ARGUMENT'
    elif 'PERMISSION_DENIED' in raw_message:
        error_reason = 'PERMISSION_DENIED'
    elif 'RESOURCE_EXHAUSTED' in raw_message:
        error_reason = 'RESOURCE_EXHAUSTED'
    elif 'INTERNAL' in raw_message or '500' in raw_message:
        error_reason = 'INTERNAL_ERROR'
    elif 'NOT_FOUND' in raw_message or '404' in raw_message:
        error_reason = 'NOT_FOUND'
    elif 'UNAVAILABLE' in raw_message or '503' in raw_message:
        error_reason = 'SERVICE_UNAVAILABLE'

    error_record["error_reason"] = error_reason
    error_record["error_code"] = error_code

    # Categorize failure type
    if error_reason in ['RATE_LIMIT_EXCEEDED', 'TIMEOUT', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR']:
        error_record["failure_category"] = "transient"
    elif error_reason in ['API_KEY_INVALID', 'PERMISSION_DENIED', 'NOT_FOUND']:
        error_record["failure_category"] = "permanent"
    elif error_reason in ['CONTENT_FILTER', 'INVALID_ARGUMENT']:
        error_record["failure_category"] = "request_specific"
    else:
        error_record["failure_category"] = "unknown"

    return error_record


def verify_no_secrets(text: str, known_secrets: list[str]) -> bool:
    """
    Verify that text does not contain any known secrets.

    Args:
        text: Text to check
        known_secrets: List of secret strings to search for

    Returns:
        True if no secrets found, False otherwise
    """
    for secret in known_secrets:
        if secret and secret in text:
            return False
    return True
