"""
Database session management.
"""

import os
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
