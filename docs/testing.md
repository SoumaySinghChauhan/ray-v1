# Testing

## Test database isolation

`pytest tests/` must never touch the real development database
(`ray_v1.db`). It did, twice, before this was fixed: several integration
tests (`tests/integration/test_restart_safety.py` and others) import
`database.session`'s shared `SessionLocal`/`engine` directly, and one
test's fixture teardown deleted every row from the execution, webhook,
outcome, and contact-count tables. Running the full suite silently wiped
real operational data — including a verified recovered Payment Link —
during both the Prompt 10 and Prompt 11 sessions.

### How tests get their database

`tests/conftest.py` sets `DATABASE_URL` to a throwaway SQLite file in a
fresh `tempfile.mkdtemp()` directory before pytest collects any test
module. Because conftest.py always loads before the test files beneath it,
this happens before `from database.session import ...` runs anywhere —
`database/session.py`'s module-level `create_engine(DATABASE_URL, ...)`
call binds to the isolated file, not `ray_v1.db`. The temp directory is
removed on interpreter exit via `atexit`.

`conftest.py` uses `os.environ.setdefault(...)`, so an operator-provided
`DATABASE_URL` is respected rather than silently overridden.

### The backstop: fail-fast, not silent

If the isolation above is ever bypassed — a missing fixture, a stray
`DATABASE_URL` in the shell, a future test that skips conftest somehow —
`database/session.py` calls `assert_safe_database_url(DATABASE_URL)` at
import time, before the engine is created. It raises `RuntimeError`
immediately if the resolved URL points at `ray_v1.db` while running under
pytest (`"pytest" in sys.modules`). This guard is a no-op outside pytest,
so normal `uvicorn` runs are unaffected — production database semantics
are unchanged.

`tests/unit/test_database_isolation.py` proves both layers work:
detection of the pytest environment, correct identification of the real
dev database by filename, the guard actually raising for `ray_v1.db`
under pytest, and the live `database.session.engine` never being bound to
it during a real test run.

### Why integration tests don't need per-test database wipes

Every seeded ID used by `tests/integration/*.py` is unique to that test
(`test_restart_001`, `test_idempotency_001`, etc.), so tests don't collide
even when sharing one ephemeral database file for the whole pytest
session. `test_restart_safety.py`'s per-test teardown (deleting execution/
webhook/outcome/contact-count rows) is still safe to keep — it now cleans
up the isolated test database, never `ray_v1.db`.

### If you need to inspect what the suite actually touched

The temp database path is printed by `DATABASE_URL` inside
`database/session.py` for the duration of the run; it's deleted
automatically afterward. It is never the same file the running API server
uses.
