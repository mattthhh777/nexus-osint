---
phase: 22-repository-layer-switch-code-audit-pass-2
plan: 01
requirements-completed: [DBM-24, DBM-25, DBM-26, DBM-27, DBM-28, DBM-29, DBM-30, DBM-31]
completed: 2026-05-10
duration: "same session"
key-files:
  modified:
    - api/db.py
    - api/deps.py
    - api/main.py
    - api/services/search_service.py
    - tests/test_db.py
    - tests/test_db_stream.py
    - tests/test_db_abstraction.py
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
  created:
    - .planning/phases/22-repository-layer-switch-code-audit-pass-2/22-RMW-AUDIT.md
    - .planning/phases/22-repository-layer-switch-code-audit-pass-2/22-01-SUMMARY.md
    - .planning/phases/22-repository-layer-switch-code-audit-pass-2/22-VERIFICATION.md
---

# Phase 22 Plan 01: asyncpg Driver Swap Summary

## Result

Phase 22 is complete. Runtime DB access now uses an `asyncpg.Pool` behind the
Phase 17 `DatabaseManager` abstraction, with Postgres placeholders, explicit
transaction scopes, pool stats in `/health`, and no SQLite writer queue in DB
runtime paths.

## What Changed

- `api/db.py`
  - Uses `asyncpg.create_pool`.
  - Defaults to `min_size=2`, `max_size=10`, `command_timeout=30`.
  - Sets `idle_in_transaction_session_timeout=60s`.
  - Wraps execute, fetch, stream, and transaction helpers with `async with pool.acquire()`.
  - Wraps every acquired connection in `async with conn.transaction()`.
  - Exposes `pool_stats()` with `idle_size`.
- `api/deps.py`
  - Routes blacklist checks through the request-scoped DB dependency.
  - Falls back to singleton DB/orchestrator only when lifespan state is unavailable.
  - Preserves fail-closed blacklist behavior on DB errors.
- `api/main.py` and `api/services/search_service.py`
  - Removed stale SQLite/write-queue comments from Phase 22 runtime paths.
- Tests
  - Removed forbidden future imports from DB-layer tests.
  - Added idle transaction timeout coverage.
  - Verified DB, health, endpoint, and Phase 16 route compatibility.
- Audit
  - Added `22-RMW-AUDIT.md`; no read-modify-write update sites found.

## Verification

- `docker compose -f docker-compose.test.yml up -d test-postgres` -> healthy Postgres 16 test container.
- `python -m compileall api\deps.py api\db.py api\main.py api\services\search_service.py` -> passed.
- `python -m pytest tests/test_db.py tests/test_db_stream.py tests/test_db_abstraction.py tests/test_health.py tests/test_endpoints.py tests/integration/test_phase16_routes.py tests/test_port_searches.py -q` -> `39 passed, 2 warnings`.
- `rg -n "aiosqlite|_writer_loop|write_queue|INSERT OR|INSERT OR REPLACE|INSERT OR IGNORE|from __future__ import annotations" api\db.py api\deps.py api\main.py api\services\search_service.py tests\test_db.py tests\test_db_stream.py tests\test_db_abstraction.py` -> no matches.
- `rg -n "pool\.acquire\(" api\db.py` -> 5 matches.
- `rg -n "async with conn\.transaction\(" api\db.py` -> 5 matches.
- `rg -n "SELECT .*UPDATE|UPDATE .*SELECT|UPDATE |SELECT .*FOR UPDATE" api -g "*.py"` -> no matches.

## Requirement Status

- DBM-24: complete. `api/db.py` uses `asyncpg.Pool` with required defaults.
- DBM-25: complete. SQLite write queue architecture removed from DB runtime path.
- DBM-26: complete. Pool acquire sites all use async context managers and transactions.
- DBM-27: complete. Runtime SQL uses `$N` placeholders.
- DBM-28: complete. SQLite `INSERT OR` forms absent; blacklist uses `ON CONFLICT`.
- DBM-29: complete. RMW audit found no update sites.
- DBM-30: complete. `idle_in_transaction_session_timeout=60s` set and tested.
- DBM-31: complete. `/health` exposes DB pool `idle_size`.

## Deviations from Plan

- Added `api/deps.py` fallback handling for tests/no-lifespan contexts. Production still uses
  `application.state.db`; fallback only applies when lifespan state is unavailable.
- `tests/integration/test_rate_limiting.py::test_search_per_user_isolation` remains outside
  this phase gate. It fails because the test monkeypatches `api.main.JWT_SECRET`, while the
  limiter decodes using `api.limiter.JWT_SECRET` and therefore falls back to IP. Weakening
  limiter JWT verification to satisfy that test would reduce rate-limit bypass resistance.

## Remaining Risks

- Phase 23 must stress the asyncpg pool under 10-agent burst load and cancellation.
- Global `from __future__ import annotations` imports still exist outside Phase 22 DB paths.
