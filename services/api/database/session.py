"""
Database session management.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

from database.schema import Base
from database.models import (
    ExecutionAttemptExtended,
    WebhookEventExtended,
    RecoveryOutcomeExtended,
    ContactCount,
)

# Load environment
load_dotenv()

# Database URL (use SQLite for local testing if DATABASE_URL not set)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./ray_v1.db"  # SQLite fallback for testing
)


def _is_running_under_pytest() -> bool:
    """True whenever the current process is a pytest run (collection or execution)."""
    return "pytest" in sys.modules


def _is_the_real_dev_database(url: str) -> bool:
    """
    True if `url` resolves to the checked-in development SQLite file
    (ray_v1.db) rather than an isolated/ephemeral database.
    """
    if not url.startswith("sqlite"):
        return False
    path = url.split("///", 1)[-1] if "///" in url else url
    return Path(path).name == "ray_v1.db"


def assert_safe_database_url(url: str) -> None:
    """
    Hard safety check: refuse to bind to the real development database while
    running under pytest.

    tests/conftest.py points DATABASE_URL at an isolated, ephemeral SQLite
    file before any test module is collected. This function is the backstop
    for that isolation — if it is ever bypassed (a missing conftest fixture,
    a stray shell DATABASE_URL, a future test that skips the fixture), the
    process fails fast at import time instead of silently mutating real
    operational data. This guard is a no-op outside of pytest: normal
    `uvicorn` runs are completely unaffected.
    """
    if _is_running_under_pytest() and _is_the_real_dev_database(url):
        raise RuntimeError(
            "Refusing to run under pytest with DATABASE_URL pointing at the real "
            "development database (ray_v1.db). Tests must use an isolated database "
            "— see tests/conftest.py and docs/testing.md. This guard exists because "
            "a prior integration test's teardown wiped real operational execution/"
            "webhook/outcome data; do not bypass it."
        )


assert_safe_database_url(DATABASE_URL)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Scoped session for thread safety
db_session = scoped_session(SessionLocal)


def get_db():
    """Get database session (dependency injection for FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database (create all tables)."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully")


def drop_db():
    """Drop all tables (for testing only)."""
    Base.metadata.drop_all(bind=engine)
    print("Database dropped")
