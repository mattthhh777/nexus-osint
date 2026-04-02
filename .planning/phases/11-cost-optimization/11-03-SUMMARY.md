---
phase: 11-cost-optimization
plan: "03"
subsystem: database / user-management
tags: [streaming, memory, caching, sqlite, cost-optimization]
requirements: [COST-04, COST-07]

dependency_graph:
  requires: []
  provides:
    - "read_stream() async generator in DatabaseManager"
    - "_load_users() with mtime-based cache"
  affects:
    - "api/db.py — new read_stream method"
    - "api/main.py — _load_users, _save_users, cache state"

tech_stack:
  added: []
  patterns:
    - "AsyncGenerator with fetchmany() for memory-safe streaming"
    - "Module-level mtime cache invalidation for file-backed config"

key_files:
  created:
    - tests/test_db_stream.py
  modified:
    - api/db.py
    - api/main.py

decisions:
  - "read_stream uses fetchmany(batch_size=50) default — balances memory savings vs DB round-trips on 1GB VPS"
  - "read/read_all preserved for backward compat — small result sets stay as list return"
  - "_save_users immediately updates the cache to prevent stale reads after write"
  - "OSError + json.JSONDecodeError used instead of generic Exception per CLAUDE.md rules"

metrics:
  duration_minutes: 3
  completed_date: "2026-04-02"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 11 Plan 03: Streaming DB Reads + Cached User Loading Summary

**One-liner:** Added `read_stream()` async generator (fetchmany-based) to DatabaseManager and mtime-invalidated cache for `_load_users()` to eliminate memory spikes and redundant disk I/O.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add read_stream() async generator (TDD) | 5367e0a | api/db.py, tests/test_db_stream.py |
| 2 | Cache _load_users() with file mtime invalidation | 054a88f | api/main.py |

## What Was Built

### Task 1 — read_stream() Async Generator

`DatabaseManager.read_stream()` added to `api/db.py`:
- Uses `cursor.fetchmany(batch_size)` (default 50) so memory usage is O(batch_size) not O(rows)
- Yields one `dict` per row — callers iterate with `async for row in db.read_stream(...)`
- `AsyncGenerator[dict[str, Any], None]` return type — correctly typed for async iteration
- `read()`, `read_all()`, and `read_one()` untouched — backward compat preserved

TDD: 5 tests in `tests/test_db_stream.py` written first (RED), then implementation (GREEN), all pass.

### Task 2 — Cached _load_users()

`_load_users()` and `_save_users()` in `api/main.py` updated:
- Two module-level vars: `_users_cache: dict | None = None` and `_users_cache_mtime: float = 0.0`
- `_load_users()` calls `USERS_FILE.stat().st_mtime` and skips the JSON read if mtime unchanged
- `_save_users()` writes the file then immediately updates both cache vars — no stale window
- Replaced `except Exception as _e` with `except (OSError, json.JSONDecodeError) as e` per CLAUDE.md

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all implementations are complete and functional.

## Performance Impact

| Concern | Before | After |
|---------|--------|-------|
| Large admin log query | fetchall() loads all rows into RAM | read_stream() streams in batches of 50 |
| _load_users() on every request | stat() + read_text() + json.loads() | stat() only; full read skipped when mtime matches |

## Self-Check: PASSED

- api/db.py: FOUND
- api/main.py: FOUND
- tests/test_db_stream.py: FOUND
- Commit 5367e0a: FOUND
- Commit 054a88f: FOUND
