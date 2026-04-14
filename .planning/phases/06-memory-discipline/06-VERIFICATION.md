---
phase: 06-memory-discipline
title: Phase 06 Verification
status: partial
last_run: "2026-04-02"
---

# Phase 06 — F4: Memory Discipline — Verification

## Observable Truths

### Local (code-level) — ✅ All Verified 2026-04-02

| # | Truth | Method | Result |
|---|-------|--------|--------|
| 1 | `_serialize_breaches` caps at 200 items | Grep `MAX_BREACH_SERIALIZE = 200` in main.py | ✅ Line 663 |
| 2 | Sherlock `_check_platform` truncates body to 512KB | Grep `MAX_BODY_BYTES = 524_288` in sherlock_wrapper.py | ✅ Line 297 |
| 3 | `search_username` is `async def` | Grep `async def search_username` in sherlock_wrapper.py | ✅ Line 364 |
| 4 | No `asyncio.new_event_loop()` in sherlock_wrapper.py | Grep `new_event_loop` returns 0 | ✅ Removed |
| 5 | main.py does NOT use `asyncio.to_thread` for Sherlock | Grep `to_thread.*search_username` returns 0 | ✅ main.py:900 |
| 6 | `/health` returns `rss_mb` and `cache_entries` | Grep `rss_mb` in health endpoint | ✅ Line 1553 |
| 7 | `/health/memory` endpoint exists (admin-only) | Grep `health_memory` in main.py | ✅ Line 1565 |
| 8 | `tracemalloc.start(10)` in startup | Grep `tracemalloc.start` in main.py | ✅ Line 445 |
| 9 | All existing tests pass | `python -m pytest tests/ -v` | ✅ 23/23 (0.96s) |

### VPS (runtime) — ⏳ Pending Deployment

| # | Truth | Method | Result |
|---|-------|--------|--------|
| 10 | RSS < 200MB after startup | `curl /health` → check `rss_mb` | ⏳ |
| 11 | RSS stays < 250MB after 10 searches | `curl /health` after 10 searches | ⏳ |
| 12 | `/health/memory` returns tracemalloc data | `curl -H cookie /health/memory` → check `top_allocations` | ⏳ |
| 13 | Cache entry count visible in `/health` | `curl /health` → check `cache_entries` | ⏳ |

## VPS Verification Commands

```bash
# After deploy, run these on VPS or via curl:

# Truth 10: RSS after startup
curl -s https://nexusosint.uk/health | python3 -m json.tool | grep rss_mb

# Truth 11: After 10 searches, check RSS again
curl -s https://nexusosint.uk/health | python3 -m json.tool | grep rss_mb

# Truth 12: Admin memory endpoint (requires nx_session cookie)
curl -s -b "nx_session=<ADMIN_JWT>" https://nexusosint.uk/health/memory | python3 -m json.tool

# Truth 13: Cache entries
curl -s https://nexusosint.uk/health | python3 -m json.tool | grep cache_entries
```

## Evidence

### Test Run (2026-04-02, local)

```
============================= test session starts =============================
platform win32 -- Python 3.10.10, pytest-9.0.2
23 passed in 0.96s
==============================
```

### Files Modified

| File | Change | Lines |
|------|--------|-------|
| api/main.py | tracemalloc import + startup | +2 lines |
| api/main.py | MAX_BREACH_SERIALIZE + _serialize_breaches cap | +5 lines |
| api/main.py | Sherlock call: remove to_thread | 1 line |
| api/main.py | /health enriched (rss_mb, cache_entries) | +2 lines |
| api/main.py | /health/memory new endpoint | +34 lines |
| modules/sherlock_wrapper.py | _check_platform body truncation | +2 lines |
| modules/sherlock_wrapper.py | search_username async conversion | -8/+6 lines |
