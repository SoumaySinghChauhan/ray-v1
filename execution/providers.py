"""
Execution providers for RAY V1.

Implements Payment Link creation via Razorpay and mock providers.
"""

import hashlib
import hmac
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any

from execution.types import (
    ExecutionAttempt,
    ExecutionResult,
    ExecutionState,
)


class PaymentLinkExecutor(ABC):
    """
    Abstract interface for Payment Link execution.

    Implementations: RazorpayPaymentLinkExecutor, MockPaymentLinkExecutor
    """

    @abstractmethod
    def create_payment_link(
        self,
        merchant_id: str,
        opportunity_id: str,
        amount: float,
        currency: str,
        customer_info: dict[str, Any] | None,
        policy_version: str,
    ) -> ExecutionResult:
        """
        Create a Payment Link.

        Args:
            merchant_id: Merchant identifier
            opportunity_id: Opportunity identifier
            amount: Payment amount
            currency: Currency code (e.g., "INR")
            customer_info: Optional customer information
            policy_version: Policy version that authorized this

        Returns:
            ExecutionResult with success/failure
        """
        pass


class RazorpayPaymentLinkExecutor(PaymentLinkExecutor):
    """
    Razorpay Payment Link executor.

    Creates real Payment Links via Razorpay API (TEST MODE ONLY).
    """

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        mode: str = "test",
        expiry_hours: int = 24,
    ):
        """
        Initialize Razorpay executor.

        Args:
            key_id: Razorpay API Key ID
            key_secret: Razorpay API Key Secret
            mode: "test" or "live" (V1 only supports "test")
            expiry_hours: Payment Link expiry in hours

        Raises:
            ValueError: If mode is not "test"
        """
        if mode != "test":
            raise ValueError(
                "RAY V1 only supports Test Mode. "
                "Live mode is disabled for safety. "
                f"Received mode: {mode}"
            )

        if not key_id or not key_secret:
            raise ValueError("Razorpay credentials (key_id, key_secret) are required")

        self.key_id = key_id
        self.key_secret = key_secret
        self.mode = mode
        self.expiry_hours = expiry_hours

        # Import Razorpay SDK
        try:
            import razorpay
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        except ImportError:
            raise ImportError(
                "razorpay package is required. Install with: pip install razorpay"
            )

    def create_payment_link(
        self,
        merchant_id: str,
        opportunity_id: str,
        amount: float,
        currency: str,
        customer_info: dict[str, Any] | None,
        policy_version: str,
    ) -> ExecutionResult:
        """
        Create a Razorpay Payment Link.

        Args:
            merchant_id: Merchant identifier
            opportunity_id: Opportunity identifier
            amount: Payment amount (INR)
            currency: Currency code
            customer_info: Optional customer info (contact, email, name)
            policy_version: Policy version

        Returns:
            ExecutionResult
        """
        execution_id = str(uuid.uuid4())

        # Generate deterministic reference_id
        reference_id = self._generate_reference_id(merchant_id, opportunity_id)

        # Create Payment Link request
        try:
            # Convert amount to paise (Razorpay uses smallest currency unit)
            amount_paise = int(amount * 100)

            # Calculate expiry
            expire_by = int(
                (datetime.now(timezone.utc) + timedelta(hours=self.expiry_hours)).timestamp()
            )

            # Build request
            request_data = {
                "amount": amount_paise,
                "currency": currency,
                "reference_id": reference_id,
                "description": f"RAY Payment Recovery - {opportunity_id}",
                "expire_by": expire_by,
                "notes": {
                    "ray_opportunity_id": opportunity_id,
                    "ray_execution_id": execution_id,
                    "ray_policy_version": policy_version,
                },
            }

            # Add customer info if available
            if customer_info:
                customer_data = {}
                if "contact" in customer_info:
                    customer_data["contact"] = customer_info["contact"]
                if "email" in customer_info:
                    customer_data["email"] = customer_info["email"]
                if "name" in customer_info:
                    customer_data["name"] = customer_info["name"]

                if customer_data:
                    request_data["customer"] = customer_data

            # Call Razorpay API
            payment_link = self.client.payment_link.create(request_data)

            # Extract response
            razorpay_payment_link_id = payment_link["id"]
            short_url = payment_link.get("short_url")

            return ExecutionResult(
                success=True,
                execution_id=execution_id,
                state=ExecutionState.SUCCEEDED.value,
                razorpay_payment_link_id=razorpay_payment_link_id,
                reference_id=reference_id,
                short_url=short_url,
                error_message=None,
                error_code=None,
            )

        except Exception as e:
            # Map error to execution state
            error_message = str(e)
            error_code = self._extract_error_code(e)

            # Determine state
            state = self._determine_error_state(e)

            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                state=state,
                razorpay_payment_link_id=None,
                reference_id=reference_id,
                short_url=None,
                error_message=error_message,
                error_code=error_code,
            )

    def _generate_reference_id(self, merchant_id: str, opportunity_id: str) -> str:
        """
        Generate deterministic reference_id.

        Format: RAY-{opportunity_id}-{hash}
        """
        # Create deterministic hash
        hash_input = f"{merchant_id}:{opportunity_id}".encode()
        hash_suffix = hashlib.sha256(hash_input).hexdigest()[:8]

        # Truncate opportunity_id if too long
        opp_id_part = opportunity_id[:20] if len(opportunity_id) > 20 else opportunity_id

        return f"RAY-{opp_id_part}-{hash_suffix}"

    def _extract_error_code(self, error: Exception) -> str | None:
        """Extract error code from Razorpay exception."""
        if hasattr(error, "code"):
            return str(error.code)
        return None

    def _determine_error_state(self, error: Exception) -> str:
        """
        Determine execution state from error.

        Maps Razorpay errors to ExecutionState.
        """
        error_message = str(error).lower()

        # Validation errors
        if "validation" in error_message or "invalid" in error_message:
            return ExecutionState.FAILED.value

        # Authentication errors
        if "authentication" in error_message or "unauthorized" in error_message:
            return ExecutionState.FAILED.value

        # Duplicate reference errors
        if "duplicate" in error_message or "already exists" in error_message:
            return ExecutionState.FAILED.value

        # Network/timeout errors (ambiguous outcome)
        if "timeout" in error_message or "connection" in error_message:
            return ExecutionState.UNKNOWN.value

        # Server errors (ambiguous outcome)
        if "server error" in error_message or "500" in error_message:
            return ExecutionState.UNKNOWN.value

        # Default to FAILED for known errors
        return ExecutionState.FAILED.value


class MockPaymentLinkExecutor(PaymentLinkExecutor):
    """
    Mock Payment Link executor for testing.

    Does not call external APIs. Returns deterministic results.
    """

    def __init__(self, should_succeed: bool = True):
        """
        Initialize mock executor.

        Args:
            should_succeed: Whether to simulate success or failure
        """
        self.should_succeed = should_succeed
        self.created_links = []  # Track created links for testing

    def create_payment_link(
        self,
        merchant_id: str,
        opportunity_id: str,
        amount: float,
        currency: str,
        customer_info: dict[str, Any] | None,
        policy_version: str,
    ) -> ExecutionResult:
        """
        Mock Payment Link creation.

        Args:
            merchant_id: Merchant identifier
            opportunity_id: Opportunity identifier
            amount: Payment amount
            currency: Currency code
            customer_info: Optional customer info
            policy_version: Policy version

        Returns:
            ExecutionResult (mocked)
        """
        execution_id = str(uuid.uuid4())

        # Generate mock reference_id
        reference_id = f"MOCK-RAY-{opportunity_id[:20]}"

        if self.should_succeed:
            # Mock successful creation
            razorpay_payment_link_id = f"plink_mock_{uuid.uuid4().hex[:16]}"
            short_url = f"https://rzp.io/l/mock_{uuid.uuid4().hex[:8]}"

            # Track for testing
            self.created_links.append({
                "execution_id": execution_id,
                "merchant_id": merchant_id,
                "opportunity_id": opportunity_id,
                "razorpay_payment_link_id": razorpay_payment_link_id,
                "reference_id": reference_id,
                "amount": amount,
                "currency": currency,
            })

            return ExecutionResult(
                success=True,
                execution_id=execution_id,
                state=ExecutionState.SUCCEEDED.value,
                razorpay_payment_link_id=razorpay_payment_link_id,
                reference_id=reference_id,
                short_url=short_url,
                error_message=None,
                error_code=None,
            )
        else:
            # Mock failure
            return ExecutionResult(
                success=False,
                execution_id=execution_id,
                state=ExecutionState.FAILED.value,
                razorpay_payment_link_id=None,
                reference_id=reference_id,
                short_url=None,
                error_message="Mock execution failure",
                error_code="MOCK_ERROR",
            )


def verify_webhook_signature(
    payload_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify Razorpay webhook signature.

    Args:
        payload_body: Raw request body (bytes)
        signature: X-Razorpay-Signature header value
        secret: Webhook secret

    Returns:
        True if signature is valid, False otherwise
    """
    # Calculate HMAC-SHA256
    expected_signature = hmac.new(
        key=secret.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected_signature, signature)


def create_razorpay_executor_from_env() -> RazorpayPaymentLinkExecutor:
    """
    Create RazorpayPaymentLinkExecutor from environment variables.

    Requires:
    - RAZORPAY_MODE=test
    - RAZORPAY_KEY_ID
    - RAZORPAY_KEY_SECRET

    Returns:
        RazorpayPaymentLinkExecutor

    Raises:
        ValueError: If configuration is invalid
    """
    mode = os.getenv("RAZORPAY_MODE", "test")
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")

    if mode != "test":
        raise ValueError(
            f"RAY V1 only supports Test Mode. Set RAZORPAY_MODE=test (got: {mode})"
        )

    if not key_id:
        raise ValueError("RAZORPAY_KEY_ID environment variable is required")

    if not key_secret:
        raise ValueError("RAZORPAY_KEY_SECRET environment variable is required")

    return RazorpayPaymentLinkExecutor(
        key_id=key_id,
        key_secret=key_secret,
        mode=mode,
    )
