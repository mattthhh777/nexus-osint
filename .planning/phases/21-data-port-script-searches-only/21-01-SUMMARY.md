---
phase: 21-data-port-script-searches-only
plan: 01
requirements-completed: [DBM-20, DBM-21, DBM-22, DBM-23]
completed: 2026-05-10
duration: "same session"
key-files:
  modified:
    - scripts/port_searches.py
    - tests/test_port_searches.py
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
  created:
    - .planning/phases/21-data-port-script-searches-only/21-01-SUMMARY.md
    - .planning/phases/21-data-port-script-searches-only/21-VERIFICATION.md
---

# Phase 21 Plan 01: Idempotent Searches Port Script Summary

## Result

Phase 21 is complete. `scripts/port_searches.py` now ports only the SQLite
`searches` table into Postgres `searches`, using `asyncpg.copy_records_to_table`
in 1000-row batches with a fail-closed truncate confirmation guard.

## What Changed

- Removed forbidden `from __future__ import annotations` from Phase 21 files.
- Added explicit CLI confirmation: `--confirm-truncate truncate-and-port-searches`.
- Kept an internal `confirm_truncate` guard so programmatic calls also fail closed.
- Preserved bounded memory behavior with SQLite `fetchmany(batch_size)`.
- Converted legacy rows:
  - ISO text timestamps to timezone-aware `datetime`.
  - CSV/list `modules_run` to `TEXT[]`.
  - integer/null `success` to boolean.
  - missing/null/invalid payload to `{}` for JSONB.
  - missing/null counters to `0`.
- Added parser, conversion, guard, live Postgres copy, and idempotency tests.

## Verification

- `docker compose -f docker-compose.test.yml up -d test-postgres` -> started healthy Postgres 16 test container.
- `python -m pytest tests/test_port_searches.py -q` -> `6 passed in 0.91s`.
- `python -m pytest tests/test_db.py tests/test_db_stream.py tests/test_port_searches.py -q` -> `16 passed in 9.15s`.
- `rg -n "from __future__ import annotations" scripts\port_searches.py tests\test_port_searches.py` -> no matches.
- `python scripts\port_searches.py --sqlite nexus_osint.db --database-url postgresql+asyncpg://nexus:nexus@localhost:5433/nexusosint_test` -> exits before DB mutation with required-confirmation error.

## Requirement Status

- DBM-20: complete. Script uses `copy_records_to_table` and `BATCH_SIZE = 1000`.
- DBM-21: complete. Type fixups covered by unit and live copy tests.
- DBM-22: complete for staging/test Postgres. Row-count parity asserted after load.
- DBM-23: complete. Rerun idempotency covered by live Postgres test.

## Deviations from Plan

None - plan executed as hardened.

## Remaining Risks

- Production cutover still requires a fresh SQLite snapshot and maintenance window in Phase 24.
- Current worktree still contains Phase 22-style `api/db.py` asyncpg boundary drift from prior work; unchanged here.
