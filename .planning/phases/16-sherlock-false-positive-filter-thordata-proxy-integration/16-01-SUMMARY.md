---
phase: 16
plan: "01"
subsystem: config-and-budget
tags: [thordata, budget-tracker, config, phase16-foundation]
dependency_graph:
  requires: []
  provides: [THORDATA_PROXY_URL, THORDATA_DAILY_BUDGET_BYTES, THORDATA_PER_SEARCH_CAP_BYTES, SHERLOCK_CONFIRMED_THRESHOLD, SHERLOCK_LIKELY_THRESHOLD, api.budget]
  affects: [api/config.py, api/budget.py, tests/unit/test_budget.py, .env.example]
tech_stack:
  added: []
  patterns: [leaf-module config, in-memory UTC-reset counter, stdlib logging]
key_files:
  created: [api/budget.py, tests/unit/test_budget.py, .env.example]
  modified: [api/config.py]
decisions:
  - "Use stdlib logging not loguru: loguru absent from project stack; project uses logging.getLogger throughout"
  - "api/budget.py placed in api/ not modules/: avoids api/ to modules/ cross-layer import when health.py reads budget metrics (Pitfall 8)"
  - "Module-level globals for budget state: O(1) memory, lazy UTC reset, acceptable restart-resets-counter trade-off (D-16)"
metrics:
  duration_seconds: 386
  completed_date: "2026-05-01T01:21:14Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 1
  tests_added: 6
---

# Phase 16 Plan 01: Config + Budget Foundation Summary

**One-liner:** 6 env-var-driven Thordata/Sherlock constants added to `api/config.py` leaf module; new `api/budget.py` in-memory UTC-reset bandwidth tracker with 6 passing unit tests; `.env.example` deploy reference with placeholder-only credentials.

## What Was Built

### Task 1 -- 6 Phase 16 constants in api/config.py (commit 7b23027)

Appended after `MAX_BREACH_SERIALIZE`, before `_ALLOWED_ORIGINS`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `THORDATA_PROXY_URL` | `None` | Residential proxy URL; None = proxy disabled |
| `_THORDATA_DAILY_BUDGET_MB` | `1024` | Private intermediate (MB) |
| `THORDATA_DAILY_BUDGET_BYTES` | `1_073_741_824` | HARD circuit-breaker limit in bytes |
| `_THORDATA_PER_SEARCH_CAP_MB` | `1` | Private intermediate (MB) |
| `THORDATA_PER_SEARCH_CAP_BYTES` | `1_048_576` | Per-search abort threshold in bytes |
| `SHERLOCK_CONFIRMED_THRESHOLD` | `70` | Score >= 70 -> state="confirmed" |
| `SHERLOCK_LIKELY_THRESHOLD` | `40` | Score >= 40 -> state="likely" |

Leaf-module rule preserved: zero `from api.*` or `from modules.*` imports added.
All pre-existing constants unchanged (OATHNET_API_KEY, JWT_SECRET, RL_SEARCH_LIMIT, MAX_BREACH_SERIALIZE confirmed present).

### Task 2 -- api/budget.py + tests/unit/test_budget.py (commit a8ed908)

**Public API of api/budget.py:**

- `record_usage(bytes_used: int) -> None` -- increments `_bytes_today` and `_requests_today`; emits WARNING log when cumulative bytes exceed 50% of daily budget (SOFT threshold, D-16)
- `is_hard_limit_exceeded() -> bool` -- returns True when `_bytes_today >= THORDATA_DAILY_BUDGET_BYTES`; caller raises `HTTPException(503, Retry-After=86400)` per D-H12
- `get_metrics() -> dict` -- returns exactly 4 keys: `bytes_today_mb`, `requests_today`, `budget_remaining_pct`, `proxy_active`; admin-gated by caller (D-H14)
- `_proxy_active: bool` -- module-level flag set to True by `api/main.py` lifespan after proxy HEAD check (D-07); read by `/health/thordata` (D-19)

**Why api/ not modules/:** If budget state lived inline in `modules/sherlock_wrapper.py`, then `api/routes/health.py` would need `from modules.sherlock_wrapper import get_budget_metrics` -- creating a cross-layer `api/ -> modules/` dependency that violates the layered architecture established in Phase 15. `api/budget.py` as a shared leaf lets both `modules/` (writer) and `api/routes/` (reader) import without circular dependency.

**6 unit tests -- all pass:**

| Test | What it checks |
|------|----------------|
| `test_record_usage_increments_counters` | `_bytes_today += N`, `_requests_today += 1` |
| `test_hard_limit_exceeded_when_over_budget` | Returns True when bytes >= budget |
| `test_hard_limit_not_exceeded_under_budget` | Returns False for small usage |
| `test_utc_midnight_resets_counters` | Patching `_current_day` to yesterday triggers full reset on next call |
| `test_get_metrics_keys_exact` | Exactly 4 keys, no extras |
| `test_get_metrics_remaining_pct_clamped_at_zero` | No negative pct when over budget |

### Task 3 -- .env.example (commit 0a0fb7d)

Created at repo root with 5 documented env vars, all placeholder-only:
- `THORDATA_PROXY_URL=http://td-customer-YOUR_USER:YOUR_PASS@t.pr.thordata.net:9999`
- `THORDATA_DAILY_BUDGET_MB=1024`
- `THORDATA_PER_SEARCH_CAP_MB=1`
- `SHERLOCK_CONFIRMED_THRESHOLD=70`
- `SHERLOCK_LIKELY_THRESHOLD=40`

File is NOT gitignored (`.gitignore` blocks `.env` and `*.env`; `.env.example` does not match). Confirmed by `git check-ignore .env.example` exiting non-zero.

## Decisions Made

1. **stdlib logging instead of loguru** -- Plan specified `loguru` in `api/budget.py`. `loguru` is absent from `requirements.txt`, not installed, and not used anywhere in the existing codebase. All production code uses `logging.getLogger`. Replaced with `logging.getLogger("nexusosint.budget")` and `%s`-style format strings. Plans 02/03 must NOT add `loguru` as a dependency.

2. **Budget state in api/budget.py not modules/sherlock_wrapper.py** -- Avoids cross-layer import when health route reads metrics. Both `modules/sherlock_wrapper.py` (Plan 02 writer) and `api/routes/health.py` (Plan 03 reader) can import from `api/budget.py` without circular dependency.

3. **In-memory counters with lazy UTC reset** -- O(1) memory footprint regardless of request volume. Container restart resets counters (acceptable D-16 trade-off; persistent budget requires SQLite write queue integration, deferred to v4.2).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced loguru with stdlib logging in api/budget.py**
- **Found during:** Task 2 -- pytest collection failed with `ModuleNotFoundError: No module named 'loguru'`
- **Issue:** Plan specified `from loguru import logger` but `loguru` is absent from `requirements.txt` and not installed. All production code uses `logging.getLogger` (stdlib).
- **Fix:** Replaced with `import logging; logger = logging.getLogger("nexusosint.budget")`. Adjusted log call format from `{}` (loguru) to `%s` (stdlib).
- **Files modified:** `api/budget.py`
- **Commit:** `a8ed908`

## Known Stubs

None. All functions fully implemented. `_proxy_active` initializes to `False` by design -- correct default since proxy is not yet verified at module import time. Lifespan sets it to `True` after health check per D-07, which is Plan 03 scope.

## Test Results

- `tests/unit/test_budget.py`: **6/6 passed**
- Full suite excluding pre-existing failure: **64/64 passed**
- Pre-existing failure: `tests/test_endpoints.py::test_full_nexus_flow` -- 503 vs 200, documented in STATE.md before Phase 16, not introduced by this plan.

## Self-Check: PASSED

Files exist:
- api/config.py -- modified (confirmed via grep)
- api/budget.py -- created (confirmed importable)
- tests/unit/test_budget.py -- created (6 tests pass)
- .env.example -- created (confirmed at repo root)

Commits exist:
- 7b23027 -- feat(16-01): add 6 Phase 16 constants to api/config.py
- a8ed908 -- feat(16-01): create api/budget.py Thordata daily bandwidth tracker + 6 unit tests
- 0a0fb7d -- chore(16-01): add .env.example with Phase 16 credential-free placeholders
