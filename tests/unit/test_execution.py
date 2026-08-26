"""
Tests for execution service.

Verifies:
- Payment Link execution
- Idempotency
- State management
- Contact tracking
- Security constraints
"""

import pytest
from datetime import datetime

from execution.service import ExecutionService
from execution.providers import MockPaymentLinkExecutor
from execution.types import ExecutionState, OpportunityState
from policy.types import PolicyDecision, PolicyDecisionType, MerchantPolicy
from optimizer.core import ActionType


@pytest.fixture
def mock_executor():
    """Create mock executor."""
    return MockPaymentLinkExecutor(should_succeed=True)


@pytest.fixture
def execution_service(mock_executor):
    """Create execution service with mock executor."""
    return ExecutionService(executor=mock_executor)


@pytest.fixture
def allow_decision():
    """Create ALLOW policy decision."""
    return PolicyDecision(
        decision=PolicyDecisionType.ALLOW.value,
        opportunity_id="opp_001",
        action_type=ActionType.CREATE_PAYMENT_LINK.value,
        policy_version="1.0.0",
        evaluated_at=datetime.now().isoformat(),
        primary_reason=None,
        all_rule_results=[],
    )


@pytest.fixture
def block_decision():
    """Create BLOCK policy decision."""
    return PolicyDecision(
        decision=PolicyDecisionType.BLOCK.value,
        opportunity_id="opp_002",
        action_type=ActionType.CREATE_PAYMENT_LINK.value,
        policy_version="1.0.0",
        evaluated_at=datetime.now().isoformat(),
        primary_reason="DO_NOT_CONTACT",
        all_rule_results=[],
    )


def create_opportunity(opp_id: str, customer_id: str, amount: float) -> dict:
    """Helper to create test opportunity."""
    return {
        "opportunity_id": opp_id,
        "customer_id": customer_id,
        "merchant_id": "test_merchant",
        "amount": amount,
        "currency": "INR",
        "customer_contact": "+919876543210",
        "customer_email": "test@example.com",
        "customer_name": "Test Customer",
    }


class TestExecutionService:
    """Test execution service."""

    def test_execute_allow_action_success(
        self, execution_service, allow_decision
    ):
        """Test 1: Successful Payment Link creation for ALLOW decision."""
        opportunity = create_opportunity("opp_001", "cust_001", 10000.0)

        result = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        # Verify success
        assert result.success is True
        assert result.state == ExecutionState.SUCCEEDED.value
        assert result.razorpay_payment_link_id is not None
        assert result.reference_id is not None
        assert result.short_url is not None

        # Verify execution recorded
        execution = execution_service.get_execution(result.execution_id)
        assert execution is not None
        assert execution.opportunity_id == "opp_001"
        assert execution.amount == 10000.0

    def test_execute_block_action_rejected(
        self, execution_service, block_decision
    ):
        """Test 2: BLOCK decision rejected from execution."""
        opportunity = create_opportunity("opp_002", "cust_002", 10000.0)

        result = execution_service.execute_allowed_action(
            policy_decision=block_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        # Verify rejection
        assert result.success is False
        assert result.error_code == "POLICY_BLOCKED"
        assert result.razorpay_payment_link_id is None

    def test_idempotency_duplicate_execution(
        self, execution_service, allow_decision
    ):
        """Test 3: Duplicate execution returns existing result."""
        opportunity = create_opportunity("opp_003", "cust_003", 10000.0)

        # Update decision to match opportunity
        allow_decision.opportunity_id = "opp_003"

        # First execution
        result1 = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        # Second execution (same opportunity, policy version)
        result2 = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        # Should return same execution
        assert result1.execution_id == result2.execution_id
        assert result1.razorpay_payment_link_id == result2.razorpay_payment_link_id

        # Mock executor should have created only one link
        assert len(execution_service.executor.created_links) == 1

    def test_contact_count_incremented(
        self, execution_service, allow_decision
    ):
        """Test 4: Contact count incremented on successful execution."""
        opportunity = create_opportunity("opp_004", "cust_004", 10000.0)
        allow_decision.opportunity_id = "opp_004"

        # Initial count
        initial_count = execution_service.get_contact_count(
            "test_merchant", "cust_004", 1
        )
        assert initial_count == 0

        # Execute
        result = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        assert result.success is True

        # Contact count should be incremented
        count = execution_service.get_contact_count(
            "test_merchant", "cust_004", 1
        )
        assert count == 1

    def test_contact_count_idempotent(
        self, execution_service, allow_decision
    ):
        """Test 5: Contact count not incremented on duplicate execution."""
        opportunity = create_opportunity("opp_005", "cust_005", 10000.0)
        allow_decision.opportunity_id = "opp_005"

        # First execution
        result1 = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )
        assert result1.success is True

        # Second execution (duplicate)
        result2 = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )
        assert result2.success is True

        # Contact count should still be 1
        count = execution_service.get_contact_count(
            "test_merchant", "cust_005", 1
        )
        assert count == 1

    def test_opportunity_state_updated(
        self, execution_service, allow_decision
    ):
        """Test 6: Opportunity state updated to ACTION_EXECUTED."""
        opportunity = create_opportunity("opp_006", "cust_006", 10000.0)
        allow_decision.opportunity_id = "opp_006"

        result = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        assert result.success is True

        # Opportunity state should be ACTION_EXECUTED
        state = execution_service.get_opportunity_state("opp_006")
        assert state == OpportunityState.ACTION_EXECUTED.value

    def test_invalid_action_rejected(
        self, execution_service, allow_decision
    ):
        """Test 7: Invalid action type rejected."""
        opportunity = create_opportunity("opp_007", "cust_007", 10000.0)
        allow_decision.action_type = ActionType.DO_NOTHING.value

        result = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        assert result.success is False
        assert result.error_code == "INVALID_ACTION"


class TestMockExecutor:
    """Test mock executor."""

    def test_mock_executor_success(self):
        """Test 8: Mock executor returns success."""
        executor = MockPaymentLinkExecutor(should_succeed=True)

        result = executor.create_payment_link(
            merchant_id="test_merchant",
            opportunity_id="opp_mock_1",
            amount=5000.0,
            currency="INR",
            customer_info=None,
            policy_version="1.0.0",
        )

        assert result.success is True
        assert result.state == ExecutionState.SUCCEEDED.value
        assert result.razorpay_payment_link_id.startswith("plink_mock_")
        assert result.short_url.startswith("https://rzp.io/l/mock_")

    def test_mock_executor_failure(self):
        """Test 9: Mock executor returns failure."""
        executor = MockPaymentLinkExecutor(should_succeed=False)

        result = executor.create_payment_link(
            merchant_id="test_merchant",
            opportunity_id="opp_mock_2",
            amount=5000.0,
            currency="INR",
            customer_info=None,
            policy_version="1.0.0",
        )

        assert result.success is False
        assert result.state == ExecutionState.FAILED.value
        assert result.razorpay_payment_link_id is None
        assert result.error_message == "Mock execution failure"


class TestExecutionResolution:
    """Test execution resolution methods."""

    def test_get_execution_by_reference_id(
        self, execution_service, allow_decision
    ):
        """Test 10: Resolve execution by reference_id."""
        opportunity = create_opportunity("opp_010", "cust_010", 10000.0)
        allow_decision.opportunity_id = "opp_010"

        result = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        # Resolve by reference_id
        execution = execution_service.get_execution_by_reference_id(
            result.reference_id
        )
        assert execution is not None
        assert execution.execution_id == result.execution_id
        assert execution.opportunity_id == "opp_010"

    def test_get_execution_by_payment_link_id(
        self, execution_service, allow_decision
    ):
        """Test 11: Resolve execution by Payment Link ID."""
        opportunity = create_opportunity("opp_011", "cust_011", 10000.0)
        allow_decision.opportunity_id = "opp_011"

        result = execution_service.execute_allowed_action(
            policy_decision=allow_decision,
            opportunity=opportunity,
            simulated_day=1,
        )

        # Resolve by Payment Link ID
        execution = execution_service.get_execution_by_payment_link_id(
            result.razorpay_payment_link_id
        )
        assert execution is not None
        assert execution.execution_id == result.execution_id
        assert execution.opportunity_id == "opp_011"


class TestRazorpayExecutorSecurity:
    """Test Razorpay executor security constraints."""

    def test_live_mode_rejected(self):
        """Test 12: Live mode is rejected."""
        from execution.providers import RazorpayPaymentLinkExecutor

        with pytest.raises(ValueError, match="only supports Test Mode"):
            RazorpayPaymentLinkExecutor(
                key_id="rzp_test_key",
                key_secret="test_secret",
                mode="live",
            )

    def test_missing_credentials_rejected(self):
        """Test 13: Missing credentials rejected."""
        from execution.providers import RazorpayPaymentLinkExecutor

        with pytest.raises(ValueError, match="credentials.*required"):
            RazorpayPaymentLinkExecutor(
                key_id="",
                key_secret="",
                mode="test",
            )

    def test_env_loader_requires_test_mode(self, monkeypatch):
        """Test 14: Environment loader requires test mode."""
        from execution.providers import create_razorpay_executor_from_env

        monkeypatch.setenv("RAZORPAY_MODE", "live")
        monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
        monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret")

        with pytest.raises(ValueError, match="only supports Test Mode"):
            create_razorpay_executor_from_env()
