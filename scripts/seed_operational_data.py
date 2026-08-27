#!/usr/bin/env python
"""Seed safe synthetic operational data for the RAY V1 API. Idempotent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))

from database.session import SessionLocal, init_db
from seed import seed_operational_data


def main():
    init_db()
    db = SessionLocal()
    try:
        result = seed_operational_data(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
