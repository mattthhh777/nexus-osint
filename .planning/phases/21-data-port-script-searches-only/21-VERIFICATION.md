---
phase: 21-data-port-script-searches-only
status: passed
verified: 2026-05-10
requirements: [DBM-20, DBM-21, DBM-22, DBM-23]
---

# Phase 21 Verification

## Goal

Create a one-way, idempotent data port for historical SQLite `searches` rows into
Postgres `searches`.

## Result

Passed. The implementation meets the Phase 21 goal and all mapped requirements.

## Must-Haves

| Requirement | Status | Evidence |
|---|---|---|
| DBM-20 | PASS | `BATCH_SIZE = 1000`; `copy_records_to_table` used in `scripts/port_searches.py`. |
| DBM-21 | PASS | Unit tests cover timestamp, modules, payload, null counters, and boolean defaults. |
| DBM-22 | PASS | Live Postgres test asserts source count equals destination count after load. |
| DBM-23 | PASS | Live Postgres test runs the port twice against the same target and confirms stable row count. |

## Automated Checks

- `python -m pytest tests/test_port_searches.py -q` -> `6 passed in 0.91s`.
- `python -m pytest tests/test_db.py tests/test_db_stream.py tests/test_port_searches.py -q` -> `16 passed in 9.15s`.
- `rg -n "from __future__ import annotations" scripts\port_searches.py tests\test_port_searches.py` -> no matches.
- CLI without `--confirm-truncate truncate-and-port-searches` exits before connecting/mutating.

## Human Verification

None required for Phase 21. Production run remains Phase 24 cutover work.
