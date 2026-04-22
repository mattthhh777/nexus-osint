---
phase: 15-refactor-main-py-layers
plan: 01
subsystem: api
tags: [pydantic, schemas, refactor, layered-architecture, fastapi]

# Dependency graph
requires:
  - phase: 14-v41-breach-cards
    provides: stable api/main.py baseline (1770 lines, 62-1 passing tests)
provides:
  - api/schemas.py — leaf module with LoginRequest + SearchRequest (all 3 validators)
  - api/main.py with zero inline Pydantic models, re-imports from api.schemas
  - Clean import contract: schemas is LEAF (no internal imports)
affects: [15-02-deps, 15-03-services, 15-04-routes, 15-05-factory]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "schemas.py as leaf module: imports only re + pydantic, zero api/* or modules/* imports"
    - "Re-export via import: from api.schemas import X in main.py keeps call sites unchanged"

key-files:
  created:
    - api/schemas.py
  modified:
    - api/main.py

key-decisions:
  - "schemas.py is a LEAF: no imports from api/* or modules/*, only re + pydantic (per CONTEXT.md import contract)"
  - "Pydantic import in main.py trimmed to ValidationError only (BaseModel + field_validator no longer needed)"
  - "import re kept in main.py (used in detect_type, _validate_id guards at lines 710–714, 1426, 1459, 1629)"
  - "Pre-existing test failure (test_full_nexus_flow) documented as out-of-scope — pre-existed before Phase 15"

patterns-established:
  - "Leaf module pattern: api/schemas.py imports only stdlib + third-party, never api/* or modules/*"
  - "Re-export pattern: importing into main.py makes names available to existing call sites without code changes"

requirements-completed: [REFACTOR-15-STEP-1]

# Metrics
duration: 20min
completed: 2026-04-22
---

# Phase 15 Plan 01: schemas.py Extraction Summary

**Extracted LoginRequest + SearchRequest (with 3 field validators) from api/main.py into api/schemas.py leaf module; main.py re-imports both names; zero test regressions introduced (61/61 refactor-scope tests green)**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-22T12:20:00Z
- **Completed:** 2026-04-22T12:40:24Z
- **Tasks:** 2/3 fully committed; Task 3 docker smoke blocked by Docker Desktop not running
- **Files modified:** 2

## Accomplishments

- Created `api/schemas.py` (41 lines) as a leaf module: `LoginRequest` + `SearchRequest` with all 3 field validators (`sanitize_query`, `validate_mode`, `validate_sf_mode`) copied verbatim
- Removed 39 lines of inline Pydantic model definitions from `api/main.py` (lines 151–186 original); replaced with 1-line import + 2-line pointer comment
- Trimmed `from pydantic import` in `main.py` from `BaseModel, ValidationError, field_validator` to `ValidationError` only
- Added `from api.schemas import LoginRequest, SearchRequest` at line 53 in `main.py` (alongside `from api.db import db`)
- All 3 validators preserved verbatim with exact regex patterns, ValueError messages, and classmethod decorators
- Import contract enforced: `grep -E '^(from|import) (api|modules)' api/schemas.py` returns zero matches
- `from api.main import` baseline: 6 before Phase 15 → 6 after Phase 15 (monotonically non-increasing)
- `api/main.py` line count: 1770 → 1735 (net -35 lines)

## Task Commits

1. **Task 1: Create api/schemas.py** - `aa5f681` (feat)
2. **Task 2: Remove Pydantic classes from api/main.py, re-import from api.schemas** - `860f166` (feat)
3. **Task 3: Run 62/62 test gate and smoke container** — pytest PASSED (61 refactor-scope green); docker smoke BLOCKED (Docker Desktop not running — human action required)

## Files Created/Modified

- `api/schemas.py` — NEW: 41-line leaf module, LoginRequest + SearchRequest with 3 validators
- `api/main.py` — MODIFIED: deleted lines 151–186 (2 Pydantic classes), added import line 53, trimmed pydantic import line 43

## Line Ranges Removed from main.py

Original lines deleted (pre-Phase-15 numbering):
- Line 149–186: entire `# ── Models ──` section (LoginRequest class, SearchRequest class with 3 validators)
- Line 43 change: `from pydantic import BaseModel, ValidationError, field_validator` → `from pydantic import ValidationError`

Replaced by:
- Line 43: `from pydantic import ValidationError`
- Line 53 (new): `from api.schemas import LoginRequest, SearchRequest  # I/O models — defined in leaf module`
- Lines 150–152 (new): 3-line pointer comment replacing the class bodies

## New File Footprint

```
api/schemas.py: 41 lines
  - 1 module docstring
  - 2 import lines
  - class LoginRequest: 3 lines
  - class SearchRequest: 35 lines (fields + 3 validators)
```

## Pytest Result

```
61 passed, 1 failed (pre-existing) — exit code 1
```

**Refactor scope:** 61/61 tests green. The 1 pre-existing failure (`test_full_nexus_flow` — asserts login 200 but gets 401) was confirmed to pre-exist before Phase 15 by reverting to commit `6f4b8ba` and re-running. This test was already failing before any Phase 15 change. The plan's stated "62 passed" appears to be aspirational — actual baseline was 61.

## Docker Smoke Result

BLOCKED — Docker Desktop daemon not running on this Windows machine at task execution time.

Steps completed:
- `docker compose build` — NOT RUN (daemon unavailable)
- `docker compose up -d` — NOT RUN
- `curl http://localhost:8000/health` — NOT RUN
- Login + search smoke — NOT RUN

Required action: Start Docker Desktop, then run:
```bash
docker compose build
docker compose up -d
curl -fsS http://localhost:8000/health
curl -fsS -c /tmp/nx.cookie -X POST http://localhost:8000/api/login -H "Content-Type: application/json" -d '{"username":"admin","password":"<APP_PASSWORD>"}'
curl -fsS -b /tmp/nx.cookie -X POST http://localhost:8000/api/search -H "Content-Type: application/json" -d '{"query":"test@example.com","mode":"automated","modules":[]}' --max-time 3
docker compose down
```

## Baseline vs Final `from api.main import` Reference Counts

| Point | Count | Notes |
|-------|-------|-------|
| Before Phase 15 (baseline) | 6 | All in tests/ — 1 in test_endpoints.py, 5 in unit/test_security_gates.py |
| After Task 2 | 6 | No new references added — monotonically non-increasing (satisfies CONTEXT.md DoD item 6) |

## Decisions Made

- Kept `import re` in `main.py` (still used in `detect_type`, `_validate_id`, and other guards throughout the file — not safe to remove)
- Did not modify any test files (Task 2 acceptance criteria note: no test rewrites needed since `LoginRequest`/`SearchRequest` were not imported from `api.main` by tests — they imported `app`, `_create_token`, `_decode_token` only)
- Pre-existing test failure (`test_full_nexus_flow`) logged as out-of-scope deviation, not fixed

## Deviations from Plan

### Pre-existing Issue (Not Introduced)

**1. [Out of Scope — Pre-existing] test_full_nexus_flow was already failing before Phase 15**
- **Found during:** Task 3 (pytest run)
- **Issue:** Test asserts `login_res.status_code == 200` but receives 401. Pre-existed at commit `6f4b8ba` (before any Phase 15 code)
- **Fix:** Not fixed — out of scope per CLAUDE.md deviation rules (pre-existing, unrelated to schemas extraction)
- **Impact on refactor:** None — the test does not import `LoginRequest` or `SearchRequest` from `api.main`; it imports `app`, `_create_token`, `_decode_token` which are still in `api/main.py`

### Docker Smoke Blocked (Infrastructure Gate)

**2. [Infrastructure Gate] Docker Desktop not running — smoke test blocked**
- **Found during:** Task 3
- **Issue:** `docker compose build` cannot connect to Docker daemon
- **Action required:** Start Docker Desktop, then run smoke steps manually (commands above)
- **Impact on plan:** Task 3 python/pytest gate PASSED; docker smoke PENDING human action

---

**Total deviations:** 2 noted (1 pre-existing test failure out of scope, 1 infrastructure gate)
**Impact on plan:** The schemas extraction itself is complete and correct. Docker smoke is a verification-only step — the code changes are correct and the Python import chain is verified.

## Known Stubs

None — this plan contains no stub values, placeholder text, or unwired data sources. Pure structural refactor.

## Issues Encountered

Docker Desktop not running at execution time. Docker smoke steps (Task 3 items 2–7) require Docker daemon. All non-docker verification passed.

## Next Phase Readiness

- `api/schemas.py` leaf module established — unblocks Step 2 (`15-02-PLAN.md`: extract `deps.py`)
- Import contract enforced (schemas is LEAF)
- 61 tests green (pre-existing 1 failure is not a blocker for refactor progression)
- Docker smoke should be run once Docker Desktop is started (commands in "Docker Smoke Result" section)
- Step 2 can proceed: `deps.py` extraction is independent of docker smoke on schemas

---
*Phase: 15-refactor-main-py-layers*
*Completed: 2026-04-22*
