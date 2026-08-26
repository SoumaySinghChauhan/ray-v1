"""
Initialize RAY V1 database.

Creates all tables required for persistent execution and webhook state.
"""

import sys
import os

# Get the Ray root directory
ray_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ray_root, 'services', 'api'))

from database.session import init_db, engine
from database.schema import Base
from database.models import (
    ExecutionAttemptExtended,
    WebhookEventExtended,
    RecoveryOutcomeExtended,
    ContactCount,
)


def main():
    """Initialize database tables."""
    print("RAY V1 - Database Initialization")
    print("=" * 50)
    print()

    print(f"Database URL: {engine.url}")
    print()

    print("Creating tables...")
    init_db()

    print()
    print("Tables created:")
    print("  - execution_attempts_extended")
    print("  - webhook_events_extended")
    print("  - recovery_outcomes_extended")
    print("  - contact_counts")
    print()

    print("✅ Database initialization complete!")
    print()
    print("Persistent state ready:")
    print("  - ExecutionAttempt: Survives restart")
    print("  - WebhookEvent: Duplicate detection across restarts")
    print("  - RecoveryOutcome: Outcome persistence")
    print("  - ContactCount: Policy enforcement across restarts")


if __name__ == "__main__":
    main()
