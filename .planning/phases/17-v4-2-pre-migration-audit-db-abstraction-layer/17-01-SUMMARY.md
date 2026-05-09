# 17-01 Summary - SQL Audit Baseline

**Status:** Complete
**Date:** 2026-05-08

## Outputs

- `SQL_INVENTORY.md` created with 25 production SQL statements inventoried under `api/`.
- `PLACEHOLDER_MAP.md` created with 10 production placeholder sites mapped from `?` to `$N`.
- `api/services/search_service.py` quota retention no longer uses SQLite-only implicit row identifiers.
- `api/db.py` now creates `quota_log.id INTEGER PRIMARY KEY` and rebuilds legacy `quota_log` tables that predate the explicit id.
- `tests/test_db.py` covers "200 inserts -> 100 newest remain" and legacy `quota_log` migration.

## Verification

- `pytest -q tests\test_db.py tests\test_db_abstraction.py`: 13 passed.
- `rg -n "rowid|AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(" api tests -S`: only `api\db.py` `AUTOINCREMENT` remains, deferred to Phase 19.
