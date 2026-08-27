"""Pytest configuration and fixtures."""

import atexit
import os
import shutil
import tempfile
import pytest
from decimal import Decimal
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services" / "api"))
sys.path.insert(0, str(project_root / "config"))

# ============================================================================
# Test database isolation
# ============================================================================
#
# database/session.py falls back to sqlite:///./ray_v1.db — the real,
# checked-in development database — whenever DATABASE_URL is unset. Several
# integration tests (tests/integration/test_restart_safety.py and friends)
# import that module's shared SessionLocal/engine directly, and one of them
# deletes rows in its teardown. Left unhandled, running `pytest tests/`
# mutates and destroys real operational data.
#
# Fix: point DATABASE_URL at a throwaway SQLite file in a fresh temp
# directory before any test module is collected (conftest.py is always
# imported ahead of test collection, so this runs before
# `from database.session import ...` executes anywhere). `setdefault` means
# an operator-provided DATABASE_URL is respected rather than silently
# overridden — if that provided value happens to be the real dev database,
# database/session.py's own assert_safe_database_url() guard will raise
# rather than continue silently. See docs/testing.md.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="ray_test_db_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_DIR}/test_ray_v1.db")
atexit.register(shutil.rmtree, _TEST_DB_DIR, True)


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
