---
phase: 09-f7-security-hardening
plan: 01
subsystem: auth
tags: [jwt, pydantic, fastapi, sqlite, security, input-validation]

requires:
  - phase: 07-f6-stack-modernization
    provides: asynccontextmanager lifespan, DatabaseManager WAL+queue, pytest baseline

provides:
  - "_validate_jwt_secret() lifespan guard — sys.exit(1) on missing/weak JWT_SECRET"
  - "Fail-closed _check_blacklist — HTTP 503 on DB read failure (no fail-open)"
  - "SpiderFootTarget Pydantic v2 validator — FQDN/IPv4 only, rejects all else"
  - "MAX_USERS cap on /api/admin/users — HTTP 403 at capacity"
  - "28 passing unit tests covering all four gates"

affects:
  - 09-02-PLAN (slowapi rate limiting builds on hardened base)
  - any phase touching auth endpoints or SpiderFoot scan dispatch

tech-stack:
  added: []
  patterns:
    - "Fail-closed exception handling: (aiosqlite.Error, OSError, ValueError, RuntimeError) -> HTTP 503"
    - "Rate-limited warning log: _last_blacklist_warn[0] monotonic clock guard (once/60s)"
    - "Dependency override pattern for TestClient tests that bypass DB-dependent auth"
    - "Top-level module import in test files to prevent load_dotenv() re-execution after monkeypatch.delenv"

key-files:
  created:
    - modules/spiderfoot_wrapper.py (SpiderFootTarget, _FQDN_RE, _IPV4_RE)
  modified:
    - api/main.py (_validate_jwt_secret wired, JWT_SECRET var, MAX_USERS cap, _check_blacklist fail-closed, SpiderFootTarget import+use)
    - tests/unit/test_security_gates.py (GREEN: top-level import, dependency_overrides for D-12)

key-decisions:
  - "JWT_SECRET read at module level via os.environ.get — load_dotenv() already set it; _validate_jwt_secret() called in lifespan to fail-hard before serving any request"
  - "_check_blacklist catches RuntimeError in addition to aiosqlite.Error/OSError/ValueError — covers DB-not-started case in test and early-boot scenarios"
  - "D-12 tests use app.dependency_overrides[get_admin_user] instead of TestClient with lifespan — avoids event-loop mismatch between pytest-asyncio and TestClient's internal loop"
  - "Test file imports api.main at module top level — prevents load_dotenv() from re-populating JWT_SECRET after monkeypatch.delenv inside test function body"

requirements-completed: [F7-D09, F7-D10, F7-D11, F7-D12, FIND-03, FIND-06, FIND-07]

duration: 20min
completed: 2026-04-07
---

# Phase 09 Plan 01: F7 Security Hardening — Wave 1 Backend Safety Gates

**Four fail-hard/fail-closed backend security gates: JWT_SECRET startup guard, blacklist fail-closed on DB error, SpiderFoot FQDN/IPv4 input validator, and MAX_USERS registration cap — all tested with 28 green unit tests.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-07T02:06:00Z
- **Completed:** 2026-04-07T02:26:09Z
- **Tasks:** 2 (TDD — RED already committed, GREEN implemented here)
- **Files modified:** 3

## Accomplishments

- D-09/FIND-03: `_validate_jwt_secret()` wired as first call in lifespan startup — process exits(1) on None, empty, or any of the 5 weak defaults (case-insensitive). `JWT_SECRET` now a proper module-level variable so `_create_token`/`_decode_token` work without NameError.
- D-10/FIND-06: `_check_blacklist` no longer fails open. Any `aiosqlite.Error`, `OSError`, `ValueError`, or `RuntimeError` raises `HTTPException(503, "security policy unavailable")` with rate-limited logging. The comment "Fails open on DB error" and the word "fail-open" are gone from the codebase.
- D-11: `SpiderFootTarget` Pydantic v2 model with `field_validator` added to `modules/spiderfoot_wrapper.py`. Accepts `example.com`, `sub.example.co.uk`, `192.168.1.1`. Rejects IPv6, CIDR, URL schemes, path traversal, non-ASCII unicode, empty strings. Wired at the SpiderFoot dispatch site in `_stream_search`.
- D-12/FIND-07: `/api/admin/users` checks `len(users) >= MAX_USERS` before insert and raises `HTTPException(403, "registration capacity reached")`. `MAX_USERS` defaults to 50, overridable via env.

## Task Commits

1. **Task 1: JWT_SECRET guard + D-10/D-11 wiring (api/main.py)** — `2157c85` (feat)
2. **Task 2: SpiderFootTarget validator** — `266390f` (feat)
3. **Task tests GREEN** — `091da24` (feat)

## Files Created/Modified

- `api/main.py` — JWT_SECRET var, _validate_jwt_secret() in lifespan, MAX_USERS cap, _check_blacklist fail-closed, SpiderFootTarget import+ValidationError catch
- `modules/spiderfoot_wrapper.py` — SpiderFootTarget BaseModel with field_validator (FQDN/IPv4 regexes)
- `tests/unit/test_security_gates.py` — Top-level `import api.main`, D-12 tests rewritten with `dependency_overrides` (sync, no event-loop issues)

## Decisions Made

- **JWT_SECRET at module level**: `JWT_SECRET = os.environ.get("JWT_SECRET", "")` — `load_dotenv()` runs at import, so the value is available immediately. The lifespan guard calls `_validate_jwt_secret()` to enforce non-empty/non-weak, then the already-set module-level var is used by `_create_token`/`_decode_token`.
- **RuntimeError in _check_blacklist**: Added alongside `aiosqlite.Error` to handle the "DB not started" case. Keeps the fail-closed guarantee even in test environments where the DB hasn't been initialized.
- **dependency_overrides for D-12 tests**: TestClient doesn't run the FastAPI lifespan by default, so `_db` is never started. Using `app.dependency_overrides[get_admin_user]` bypasses auth entirely, letting the test focus on the MAX_USERS logic only.
- **Top-level `import api.main` in test file**: `load_dotenv()` in `api/main.py` is called at first import. If each test function did `from api.main import _validate_jwt_secret` as the first import, `load_dotenv()` would run AFTER `monkeypatch.delenv("JWT_SECRET")`, re-setting the env var. Eager top-level import ensures `load_dotenv()` runs once before any test monkeypatching.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JWT_SECRET was used but never assigned as a Python variable**
- **Found during:** Task 1 analysis
- **Issue:** `_create_token` and `_decode_token` referenced `JWT_SECRET` as a Python name, but only `_JWT_SECRET_VALUE` was defined as a placeholder. At runtime this would raise `NameError`.
- **Fix:** Replaced `_JWT_SECRET_VALUE` placeholder with `JWT_SECRET: str = os.environ.get("JWT_SECRET", "")` at module level — consistent with how all other config vars work.
- **Files modified:** api/main.py
- **Committed in:** 2157c85

**2. [Rule 1 - Bug] _check_blacklist didn't catch RuntimeError from DB-not-started**
- **Found during:** Task 2 (D-10 test execution)
- **Issue:** `_db.read_one()` raises `RuntimeError("DatabaseManager not started")` when the DB hasn't been initialized. The except clause only caught `aiosqlite.Error`, so RuntimeError propagated as HTTP 500 instead of 503.
- **Fix:** Added `RuntimeError` to the except tuple in `_check_blacklist`.
- **Files modified:** api/main.py
- **Committed in:** 2157c85

**3. [Rule 1 - Bug] Test monkeypatching race with load_dotenv()**
- **Found during:** Task 1 test execution (RED tests not becoming GREEN)
- **Issue:** Tests called `monkeypatch.delenv("JWT_SECRET")` then `from api.main import _validate_jwt_secret`. The import triggered `load_dotenv()` which re-set `JWT_SECRET` in `os.environ`, defeating the monkeypatch.
- **Fix:** Added `import api.main` at the top of the test module so `load_dotenv()` runs once at collection time, before any test monkeypatching.
- **Files modified:** tests/unit/test_security_gates.py
- **Committed in:** 091da24

**4. [Rule 1 - Bug] D-12 tests used pytest.mark.asyncio + tmp_db fixture with TestClient**
- **Found during:** Task 1 test execution
- **Issue:** `tmp_db` (pytest-asyncio fixture) runs in a different event loop than TestClient's internal loop. On teardown, `asyncio.wait_for(writer_task)` fails with "belongs to a different loop".
- **Fix:** Rewrote D-12 tests as synchronous functions using `app.dependency_overrides[get_admin_user]` to bypass auth, testing only the MAX_USERS endpoint logic.
- **Files modified:** tests/unit/test_security_gates.py
- **Committed in:** 091da24

---

**Total deviations:** 4 auto-fixed (all Rule 1 — bugs found during implementation/test execution)
**Impact on plan:** All fixes essential for correctness and test reliability. No scope creep. Plan's behavioral requirements fully met.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Known Stubs

None — all four gates are fully implemented, not stubbed.

## Next Phase Readiness

- Wave 1 gates shipped and tested: D-09, D-10, D-11, D-12 all green
- Wave 2 (09-02): slowapi rate limiting per endpoint + per user can proceed against this hardened base
- No blockers

---
*Phase: 09-f7-security-hardening*
*Completed: 2026-04-07*
