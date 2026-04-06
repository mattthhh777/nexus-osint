---
phase: 07-f6-stack-modernization
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, httpx, jwt, pyjwt, asgi, fastapi, rollback, deploy]

# Dependency graph
requires:
  - phase: 06-memory-discipline
    provides: /health endpoint with rss_mb + psutil instrumentation
provides:
  - "4-test green baseline on Python 3.10 (current) — gate for Plan 03 Python 3.12 upgrade"
  - "test_health_endpoint: GET /health via ASGITransport, asserts status + rss_mb"
  - "test_jwt_roundtrip: _create_token/_decode_token roundtrip + tamper → 401 verification"
  - "DEPLOY.md: complete Python 3.12 rollback runbook matching CLAUDE.md §F6 template"
affects:
  - 07-02 (tenacity removal + FIND-16 fix — same branch, same test gate)
  - 07-03 (Python 3.12 Dockerfile upgrade — gated on this plan's outputs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "httpx.ASGITransport pattern for FastAPI endpoint tests (no live server needed)"
    - "tmp_db fixture + dependency_overrides for isolated endpoint testing"
    - "Direct _create_token/_decode_token import for pure unit JWT tests (no HTTP overhead)"

key-files:
  created:
    - tests/test_endpoints.py
    - DEPLOY.md
  modified: []

key-decisions:
  - "D-01: 4 green tests on current Python establish F6 test gate — Plan 03 cannot proceed without exit-0"
  - "D-02: DEPLOY.md rollback runbook matches CLAUDE.md §F6 template verbatim — pre-py312-backup tag + pip freeze mandatory before Dockerfile change"
  - "test_jwt_roundtrip is a pure unit test (no DB, no HTTP) — validates PyJWT HS256 stays compatible through upgrade"

patterns-established:
  - "TDD pattern for FastAPI: write tests against existing endpoints, confirm baseline, then upgrade"
  - "Rollback runbook gate: DEPLOY.md must exist and be committed before any base-image change"

requirements-completed: [F6-TEST-GATE, F6-ROLLBACK]

# Metrics
duration: 8min
completed: 2026-04-06
---

# Phase 07 Plan 01: Test Gate + Rollback Runbook Summary

**4-test pytest baseline (health + JWT roundtrip) + DEPLOY.md Python 3.12 rollback runbook — both F6 gates satisfied before Dockerfile upgrade in Plan 03**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-06T17:10:00Z
- **Completed:** 2026-04-06T17:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `test_health_endpoint`: GET /health via httpx.ASGITransport, asserts HTTP 200 + `status` and `rss_mb` keys present in JSON response
- Added `test_jwt_roundtrip`: pure unit test for `_create_token`/`_decode_token` — roundtrip (sub, role, exp, iat, jti), expiry check, and tampered token → HTTPException(401) verified
- Created `DEPLOY.md` with complete Python 3.12 upgrade runbook: Pre-Upgrade Snapshot, Upgrade Procedure, Rollback Procedure, Rollback Triggers, Post-Upgrade Cleanup, Known Risks — matching CLAUDE.md §F6 template verbatim

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend tests/test_endpoints.py with test_health_endpoint + test_jwt_roundtrip** - `95064cb` (test)
2. **Task 2: Write DEPLOY.md rollback runbook for Python 3.12 upgrade** - `3cf73de` (docs)

## Files Created/Modified

- `tests/test_endpoints.py` - Extended from 2 to 4 async tests; added imports for datetime/timezone, HTTPException, _create_token, _decode_token
- `DEPLOY.md` - Full Python 3.12 upgrade + rollback runbook (replaces minimal Portuguese placeholder)

## Decisions Made

- `test_jwt_roundtrip` imports `_create_token`/`_decode_token` directly (not via HTTP) — pure unit test validates PyJWT behavior without ASGI overhead; faster and more focused
- `/health` assertions use `status` + `rss_mb` (confirmed keys from Phase 06 enrichment, not guessed)
- DEPLOY.md retains original deploy prerequisites section (swap, .env, initial deploy) while adding all F6-specific rollback content

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Existing `/health` endpoint and `_create_token`/`_decode_token` implementations were complete and correct. Tests went green on first run.

Note: `tests/test_endpoints.py` was listed as `?? tests/test_endpoints.py` in git status (untracked) — the file existed locally but had never been committed. The commit `95064cb` records it as `create mode 100644`. This matches the git status shown at session start.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 03 (Python 3.12 Dockerfile upgrade) is now unblocked: 4 tests green + DEPLOY.md rollback runbook committed
- Plan 02 (tenacity removal + FIND-16 fix) can proceed in parallel — same branch, same test gate
- Both F6 prerequisite gates (D-01: test suite green, D-02: rollback documented) are satisfied

---
*Phase: 07-f6-stack-modernization*
*Completed: 2026-04-06*
