---
phase: "04"
plan: "01"
subsystem: "database"
tags: [sqlite, hardening, wal, asyncio, write-queue, tests]
dependency_graph:
  requires: []
  provides: [single-db-connection, wal-mode, write-serialization, test-suite]
  affects: [api/main.py, api/db.py, tests/]
tech_stack:
  added: [pytest>=8.0, pytest-asyncio>=0.23]
  patterns: [DatabaseManager-singleton, asyncio-Queue-write-serialization, WAL-mode, pytest-asyncio-fixtures]
key_files:
  created:
    - api/db.py (Task 1 — committed in 4ac9fae)
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_db.py
    - requirements-dev.txt
  modified:
    - api/main.py (all 9 aiosqlite.connect sites replaced)
decisions:
  - Single persistent aiosqlite connection with WAL + asyncio.Queue write serialization
  - asyncio.create_task(_log_search) removed — db.write() is already non-blocking
  - _init_audit_db() and _init_rate_table() removed — DDL consolidated in db.startup()
  - _check_rate() reads directly (WAL allows concurrent reads), writes via queue
metrics:
  duration_min: 12
  completed_date: "2026-03-31"
  tasks_completed: 4
  files_changed: 6
---

# Phase 04 Plan 01: SQLite Hardening Summary

**One-liner:** Single persistent aiosqlite connection with WAL mode and asyncio.Queue write serialization, replacing 9 scattered aiosqlite.connect sites in main.py, with a 5-test pytest suite.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Create api/db.py — DatabaseManager class | 4ac9fae | Done (pre-existing) |
| 2 | Migrate api/main.py — replace all 9 aiosqlite.connect sites | 3c2d412 | Done |
| 3 | _check_rate() atomicity rewrite | 3c2d412 | Done (implemented in Task 2) |
| 4 | Bootstrap test suite (conftest.py, test_db.py, requirements-dev.txt) | 26fe12b | Done |

## Verification Results

| Criterion | Result |
|-----------|--------|
| WAL mode active | PASS — test_wal_mode confirms `PRAGMA journal_mode = wal` |
| Zero connection sites in main.py | PASS — `grep aiosqlite.connect api/main.py` returns 0 |
| Write serialization | PASS — test_write_serialization: 50 concurrent writes, 0 errors |
| Reads non-blocking | PASS — test_read_during_write: reads return while queue has items |
| Schema consolidated | PASS — all 4 tables created in db.startup(), zero inline DDL |
| Fire-and-forget fixed | PASS — no asyncio.create_task(_log_search) in main.py |
| Tests pass | PASS — 5/5: pytest tests/test_db.py -v |
| Graceful shutdown | PASS — test_startup_shutdown_persists verifies drain + close |

## Decisions Made

1. **Tasks 2 and 3 implemented together** — the plan listed `_check_rate()` atomicity as a separate task, but it was naturally implemented during the main.py migration in Task 2. No separate commit was needed. Both the read-then-write pattern and the queue-serialized writes are in commit 3c2d412.

2. **`_revoke_token()` simplified** — removed the `try/except` wrapper since `db.write()` is fire-and-forget and logs errors internally. Token revocation failures are now logged at the db layer rather than silently swallowed.

3. **`_check_blacklist()` purge ordering** — the expired entry purge is now fire-and-forget (`db.write`) before the read. Since the queue serializes writes, the purge will run before any subsequent write, but reads execute concurrently. Acceptable: stale entries have a short expiry window and the security property (blacklisted tokens still blocked) is preserved.

4. **`admin_stats()` quota_log CREATE TABLE removed** — the inline DDL in admin_stats (workaround for schema drift) is eliminated now that schema is consolidated in db.startup().

## Deviations from Plan

### Implementation Order Change

**Found during:** Task 2 execution
**Issue:** Plan listed Task 3 (_check_rate atomicity) as separate from Task 2 (migration). In practice, implementing Task 2 required writing the new _check_rate() at the same time — there is no intermediate valid state where main.py has the new _check_rate() but still uses old aiosqlite.connect elsewhere.
**Fix:** Tasks 2 and 3 implemented in a single commit (3c2d412). The code matches the plan's Task 3 specification exactly.
**Files modified:** api/main.py
**Commit:** 3c2d412

### aiosqlite Not Imported in Original main.py (Bug — Rule 1)

**Found during:** Task 2 exploration
**Issue:** The original api/main.py used `aiosqlite.connect()` in 9 places but had no `import aiosqlite` at the top. The file would fail at runtime on first DB call. This was a pre-existing bug, likely introduced when an import was accidentally removed.
**Fix:** Eliminated by migration — no aiosqlite import needed in main.py anymore.
**Commit:** 3c2d412

## Known Stubs

None — all data flows are wired to the real DatabaseManager singleton.

## Self-Check: PASSED

| Item | Result |
|------|--------|
| api/db.py | FOUND |
| api/main.py | FOUND |
| tests/__init__.py | FOUND |
| tests/conftest.py | FOUND |
| tests/test_db.py | FOUND |
| requirements-dev.txt | FOUND |
| commit 4ac9fae | FOUND |
| commit 3c2d412 | FOUND |
| commit 26fe12b | FOUND |
