---
phase: 06-memory-discipline
plan: 06-01
title: Memory Guards + Sherlock Async + Health Instrumentation
status: complete
completed: "2026-04-02T12:20:00Z"
files_modified:
  - api/main.py
  - modules/sherlock_wrapper.py
  - .planning/codebase/CONCERNS.md
files_created:
  - .planning/phases/06-memory-discipline/06-01-PLAN.md
  - .planning/phases/06-memory-discipline/06-01-SUMMARY.md
tasks_completed: 6
---

# Summary 06-01: Memory Guards + Sherlock Async + Health Instrumentation

## Changes Made

### api/main.py (5 modifications)

1. **tracemalloc import + startup**: Added `import tracemalloc` and `tracemalloc.start(10)` in the `startup()` handler. 10 frames provides actionable stack traces for the `/health/memory` endpoint.

2. **Breach serializer memory guard**: Added `MAX_BREACH_SERIALIZE = 200` constant. `_serialize_breaches()` now takes an optional `limit` parameter and applies `breaches[:limit]`. The frontend already paginates at 25 items and uses cursor-based `/api/search/more-breaches` for the rest. This prevents OOM when OathNet returns 10K+ breaches.

3. **Sherlock call — removed `asyncio.to_thread`**: In `_stream_search`, the Sherlock call changed from `asyncio.to_thread(search_username, ...)` to direct `await search_username(...)` since `search_username` is now async.

4. **`/health` enriched**: Added `rss_mb` (process RSS via `psutil.Process()`) and `cache_entries` (TTLCache length) to the health response. Additive change — no breaking to existing consumers (Docker healthcheck).

5. **`/health/memory` new endpoint**: Admin-only (`Depends(get_admin_user)`) endpoint exposing RSS, VMS, tracemalloc current/peak, top 15 allocations by line, cache size/maxsize, and agents_paused status. For diagnosing memory leaks on the 1GB VPS.

### modules/sherlock_wrapper.py (2 modifications)

1. **Response body bounding**: In `_check_platform()`, `resp.text` is now truncated to `MAX_BODY_BYTES = 524_288` (512KB) before text matching. Prevents a single platform returning megabytes of HTML from inflating memory.

2. **Async conversion**: `search_username()` converted from sync (with deprecated `asyncio.new_event_loop()` + `asyncio.set_event_loop()`) to `async def`. The blocking `_try_sherlock_cli()` (uses `subprocess.run(timeout=120)`) is wrapped in `asyncio.to_thread()`. Direct `await _run_async_checks()` replaces the event loop creation/destruction pattern.

### .planning/codebase/CONCERNS.md (7 findings resolved)

Marked as RESOLVED with dates and phase references:
- JWT Stored in localStorage [CRITICAL] → Phase 11
- No Tests Whatsoever [CRITICAL] → Phase 04/05
- OathnetClient Uses Synchronous requests [MEDIUM] → Phase 11
- Multiple OathnetClient Instances [MEDIUM] → Phase 11
- requests Library is Redundant [LOW] → Phase 11
- SQLite as Production Database [LOW] → Phase 04
- No Test Coverage At All [CRITICAL] → Phase 04/05

## Verification

- **23/23 tests passing** (0.96s) — zero regressions
- All 7 observable truths from 06-01-PLAN are implementable and verifiable via grep/curl

## Decisions

- **D-01**: Breach serialize cap at 200 (not generator) — SSE requires complete JSON per event, generator provides no benefit. Frontend cursor pagination handles the rest.
- **D-02**: `MAX_BODY_BYTES` defined inside `_check_platform` body (not module-level constant) — scoped to the only place it's used. Can be promoted to module level if needed by other functions later.
- **D-03**: tracemalloc enabled at startup unconditionally — ~3-5% CPU overhead is acceptable per user approval on 1vCPU VPS. Can be gated behind env var in the future.
- **D-04**: `/health/memory` is admin-only (not public like `/health`) — tracemalloc snapshots expose file paths and internal structure.

## Next Steps

- Phase 06 verification (06-VERIFICATION.md) can be run once deployed to VPS
- Remaining Phase 06 work: manual RSS measurement on VPS after deployment + 10 searches
- After Phase 06 verified: Phase 07 (F6 Stack Modernization) or Phase 08 (F5 Docker) per ROADMAP
