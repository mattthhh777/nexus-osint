# 17-03 Summary - aiosqlite Containment

**Status:** Complete with unrelated suite failures
**Date:** 2026-05-08

## Refactored Files

- `api/deps.py`: removed `aiosqlite`, uses `DatabaseError`, `execute_nowait`, and `fetch_one`.
- `api/services/search_service.py`: removed `aiosqlite`, uses `DatabaseError`, `execute_nowait`, and explicit `quota_log.id` retention.
- `api/services/auth_service.py`: uses `execute_nowait` for token revocation.
- `api/routes/admin.py`: removed `aiosqlite`, uses `DatabaseError`, `fetch_one`, `fetch_all`, and `fetch_stream`.
- `api/main.py`: removed unused `aiosqlite` import and updated the DB comment.
- `tests/unit/test_security_gates.py`: updated blacklist DB-failure simulation to the Phase 17 abstraction methods.

## Verification

- `rg -n "aiosqlite" api --glob "*.py"`: only `api\db.py`.
- `rg -n "rowid|AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(" api tests -S`: only `api\db.py` `AUTOINCREMENT`, deferred to Phase 19.
- `pytest -q tests\test_db.py tests\test_db_abstraction.py`: 13 passed.
- `pytest -q`: 121 passed, 2 failed, 5 warnings.

## Residual Failures

- `tests/integration/test_rate_limiting.py::test_search_per_user_isolation`: still rate-limited by `ip:testclient`, not by user key. This is outside Phase 17 DB migration scope.
- `tests/test_endpoints.py::test_full_nexus_flow`: returns 503 because blacklist checks use the module singleton DB, while the test monkeypatches `api.main._db`; this failure is already documented in project state as pre-existing.

Phase 21 driver-swap surface is now `api/db.py` plus the documented SQL placeholder/dialect rewrites.
