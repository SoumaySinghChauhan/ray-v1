"""
Regression tests for test/development database isolation (Prompt 11.1).

Proves:
  1. pytest is reliably detectable as a test environment.
  2. The real dev database (ray_v1.db) is correctly identified by path,
     regardless of how it's referenced (relative, absolute, different cwd).
  3. Under pytest, database.session's shared engine is bound to an isolated
     database, never to ray_v1.db.
  4. The fail-fast guard actually raises if something points DATABASE_URL at
     the real dev database while pytest is running — proven by calling the
     guard directly with constructed URLs, never by attempting a real
     connection to ray_v1.db.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
API_ROOT = PROJECT_ROOT / "services" / "api"
for p in (str(PROJECT_ROOT), str(API_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from database.session import (
    engine,
    DATABASE_URL,
    _is_running_under_pytest,
    _is_the_real_dev_database,
    assert_safe_database_url,
)


def test_pytest_is_detected_as_the_running_environment():
    assert _is_running_under_pytest() is True


@pytest.mark.parametrize(
    "url,expected",
    [
        ("sqlite:///./ray_v1.db", True),
        ("sqlite:////Users/someone/Ray/ray_v1.db", True),
        ("sqlite:///services/api/ray_v1.db", True),
        ("sqlite:///./test_ray_v1.db", False),
        ("sqlite:////tmp/ray_test_db_abc123/test_ray_v1.db", False),
        ("sqlite:///:memory:", False),
        ("postgresql://postgres:postgres@localhost:5432/ray_dev", False),
    ],
)
def test_real_dev_database_is_identified_by_filename_not_by_guessing(url, expected):
    assert _is_the_real_dev_database(url) is expected


def test_fail_fast_guard_raises_for_the_real_dev_database_under_pytest():
    """
    Proves the backstop actually fires — without ever opening a connection
    to the real ray_v1.db. If this guard is ever weakened or removed, this
    test fails loudly instead of operational data silently disappearing.
    """
    with pytest.raises(RuntimeError, match="real development database"):
        assert_safe_database_url("sqlite:///./ray_v1.db")


def test_fail_fast_guard_allows_isolated_test_urls():
    # Must not raise.
    assert_safe_database_url("sqlite:///./test_ray_v1.db")
    assert_safe_database_url("sqlite:///:memory:")


def test_database_session_module_is_not_bound_to_the_real_dev_database():
    """
    The actual shared engine used by tests/integration/*.py — proves the
    conftest.py isolation is active, not just theoretically available.
    """
    resolved = str(engine.url)
    assert not _is_the_real_dev_database(resolved), f"engine bound to the real dev database: {resolved}"
    assert not _is_the_real_dev_database(DATABASE_URL), f"DATABASE_URL points at the real dev database: {DATABASE_URL}"
    assert "test_ray_v1.db" in DATABASE_URL or DATABASE_URL == "sqlite:///:memory:"
