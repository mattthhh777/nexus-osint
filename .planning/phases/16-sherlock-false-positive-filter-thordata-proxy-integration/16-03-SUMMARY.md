---
phase: 16-sherlock-false-positive-filter-thordata-proxy-integration
plan: 03
status: COMPLETE
completed: "2026-05-01"
commit: 0d3a61a
---

# Phase 16 Plan 03 Summary — Route Layer Wiring

## What Was Built

Wired Phase 16 backend primitives (Plans 01 + 02) into the live request flow across 4 files.

### 1. api/deps.py — get_optional_admin_user

New dependency that wraps `get_current_user` and returns `dict | None`. Never raises HTTPException. Admin-gated pattern for routes that need conditional enrichment without requiring auth.

**Bug discovered and fixed:** calling `get_current_user(request)` directly without DI causes `credentials` to default to the `Depends(security)` object (not `None`). Fixed by passing `credentials=None` explicitly.

### 2. search_service.py — validator + budget circuit breaker + extended SSE serializer

Sherlock branch in `_stream_search` now gates on:
1. `SherlockUsernameRequest` validator → `module_error(invalid_username)` on reject (D-H8/D-H9)
2. `api.budget.is_hard_limit_exceeded()` → `module_error(budget_exceeded, retry_after=86400)` (D-H12)

SSE event extended:
- `found_count` (confirmed only), `likely_count` (NEW), `total_checked`, `source`, `proxy_used` (NEW)
- `found`: list of `{platform, url, category, icon, state, confidence}` — exactly 6 keys
- `likely`: NEW list, same 6-key shape

`negative_markers`, `status_pts`, `text_pts`, `size_pts` NEVER serialized (D-H2/D-H3).

### 3. api/routes/health.py — Thordata admin-gated metrics

`/health` gains `maybe_admin: dict | None = Depends(get_optional_admin_user)`. When admin, response includes:
```json
{
  "thordata": {
    "bytes_today_mb": float,
    "requests_today": int,
    "budget_remaining_pct": float,
    "proxy_active": bool
  }
}
```
Non-admin response unchanged. Exactly 4 keys (D-H14). Sources from `api.budget.get_metrics()`.

### 4. api/main.py — Lifespan Thordata startup health check

`_thordata_startup_check()` awaited synchronously during startup so `_proxy_active` is set before first request lands.

Behavior:
- `THORDATA_PROXY_URL` unset → `_proxy_active = False`, INFO log
- Proxy reachable → `_proxy_active = True`, INFO log with masked URL + exit IP
- Proxy fails → `_proxy_active = False`, WARNING log with masked URL + exception type
- Logs NEVER contain `user:pass` (D-H5: `_masked_proxy_log` used exclusively)
- Never raises → app always starts (D-07 degradation-first principle)

## Test Coverage

| File | Tests | Result |
|------|-------|--------|
| tests/unit/test_schemas_phase16.py | 9 | ✅ |
| tests/integration/test_phase16_routes.py | 10 | ✅ |
| tests/unit/test_budget.py | 16 | ✅ |
| tests/unit/test_sherlock_wrapper.py | 20 | ✅ |

103 non-baseline tests green. Pre-existing failure: `test_full_nexus_flow` (503 from DB-not-started in test harness — documented in STATE.md since Phase 15).

## Key Decisions

**D-OPT-1: override `get_optional_admin_user` in tests, not `get_admin_user`**
`/health` depends on the optional variant. Overriding `get_admin_user` bypasses the wrong code path. Tests 7-8 corrected to use the right override key.

**D-OPT-2: single /health endpoint enriched conditionally, not /health/thordata route**
Avoids route proliferation. Admin enrichment on existing endpoint = single source of truth (D-19).

**D-OPT-3: lifespan check is awaited synchronously, not create_task**
10s bound on startup is acceptable for VPS. Guarantees `_proxy_active` is set before first Sherlock request lands. Fire-and-forget would race the first request.

## Acceptance Criteria Check

- [x] `grep "class SherlockUsernameRequest" api/schemas.py` — 1 match
- [x] `grep "is_hard_limit_exceeded" api/services/search_service.py` — 1 match
- [x] `grep "budget_exceeded" api/services/search_service.py` — 1 match
- [x] `grep "negative_markers" api/services/search_service.py` — 0 real matches (comment only)
- [x] `grep '"likely":' api/services/search_service.py` — 1 match
- [x] `grep '"proxy_used":' api/services/search_service.py` — 1 match
- [x] `grep "def get_optional_admin_user" api/deps.py` — 1 match
- [x] `grep '"thordata"' api/routes/health.py` — 1 match
- [x] `grep "_thordata_startup_check" api/main.py` — 2 matches (def + call)
- [x] `grep "_masked_proxy_log" api/main.py` — 1 match
- [x] All Phase 16 + project tests green (103 passed)
