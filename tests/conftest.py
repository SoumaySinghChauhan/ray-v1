"""Pytest configuration and fixtures."""

import pytest
from decimal import Decimal
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services" / "api"))
sys.path.insert(0, str(project_root / "config"))


@pytest.fixture
def sample_payment_amount():
    """Sample payment amount for tests."""
    return Decimal("1000.00")


@pytest.fixture
def sample_recovery_probability():
    """Sample recovery probability for tests."""
    return 0.35


@pytest.fixture
def sample_customer_id():
    """Sample customer ID for tests."""
    return "cust_test_12345"


@pytest.fixture
def sample_opportunity_id():
    """Sample opportunity ID for tests."""
    return "opp_test_12345"
