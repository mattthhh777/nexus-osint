---
phase: 11-cost-optimization
plan: 04
status: complete
completed: "2026-04-02"
duration_min: 4
tasks_completed: 2
files_modified: 2
commits:
  - d56e0ca  # feat(11-04): add TTL response cache for external API calls
  - 448267c  # feat(11-04): replace SpiderFoot fixed polling with exponential backoff
requirements_met:
  - COST-01
  - COST-06
subsystem: api
tags: [caching, performance, cost-optimization, spiderfoot, oathnet]
dependency_graph:
  requires:
    - 11-01  # OathnetClient async singleton (oathnet_client imported)
  provides:
    - TTL response cache for all OathNet endpoints
    - Exponential backoff for SpiderFoot polling
  affects:
    - api/main.py (_stream_search, _run_spiderfoot)
tech_stack:
  added:
    - cachetools==5.5.0 (TTLCache — pure-Python, no new C extensions)
  patterns:
    - Cache-aside pattern with query normalisation
    - Exponential backoff with cap
key_files:
  created: []
  modified:
    - api/main.py
    - requirements.txt
key_decisions:
  - "TTLCache maxsize=200 / ttl=300: 200 entries * ~10KB avg = ~2MB max memory — acceptable for 1GB VPS"
  - "Cache key normalised (lowercase + strip) so repeat queries with case variation hit same entry"
  - "Never cache error responses or None — only successful non-None API results stored"
  - "SpiderFoot backoff: 5s→10s→20s→30s (cap) — ~20 polls vs ~120, same 600s total timeout"
  - "except httpx.HTTPError replaces bare except Exception in SpiderFoot polling loop per CLAUDE.md rule"
  - "Standalone /api/oathnet/* endpoints mentioned in plan do not exist in codebase — no-op for that step"
metrics:
  duration_min: 4
  completed: "2026-04-02T02:07:42Z"
  tasks: 2
  files: 2
---

# Phase 11 Plan 04: TTL Cache + SpiderFoot Exponential Backoff Summary

## One-liner

TTLCache (5-min / 200-entry) wraps all OathNet API calls; SpiderFoot polling replaced with exponential backoff (5s→30s cap, ~20 polls vs ~120).

## What Was Done

### Task 1 — TTL Response Cache for External API Calls

Added `cachetools.TTLCache` as a module-level cache in `api/main.py` to preserve OathNet's 100 lookups/day quota:

**New infrastructure:**
- `_api_cache: TTLCache = TTLCache(maxsize=200, ttl=300)` — 5-minute TTL, max 200 entries
- `_cache_key(endpoint, query)` — normalises query (lowercase + strip) before hashing
- `_get_cached(endpoint, query)` — returns cached data or None
- `_set_cached(endpoint, query, data)` — stores only non-None successful results

**Endpoints wrapped with cache-aside pattern:**
- `breach` — wraps `oathnet_client.search_breach()`
- `stealer` — wraps `oathnet_client.search_stealer_v2()`
- `holehe` — wraps `oathnet_client.holehe()` (holehe_domains list cached)
- `discord_user` / `discord_hist` — wraps `discord_userinfo` and `discord_username_history`
- `ip_info` — wraps `oathnet_client.ip_info()`
- `steam` — wraps `oathnet_client.steam_lookup()`
- `xbox` — wraps `oathnet_client.xbox_lookup()`
- `roblox` — wraps `oathnet_client.roblox_lookup()`

**Breach+stealer parallel gather refactor:** The original `asyncio.gather([breach, stealer])` was refactored to support mixed cache-hit / API-call paths. When both are cached, no API calls are made. When one or both require API calls, only those coroutines are gathered.

### Task 2 — SpiderFoot Exponential Backoff

Replaced `for _ in range(120): await asyncio.sleep(5)` with a `while elapsed < max_elapsed` loop using exponential backoff:

```python
poll_interval = 5.0   # start at 5s
max_interval  = 30.0  # cap at 30s
max_elapsed   = 600.0 # 10 min total timeout (unchanged)
elapsed       = 0.0

while elapsed < max_elapsed:
    await asyncio.sleep(poll_interval)
    elapsed += poll_interval
    ...
    poll_interval = min(poll_interval * 2, max_interval)
```

Poll sequence: 5s, 10s, 20s, 30s, 30s, 30s... → ~20 polls to reach 600s vs ~120 fixed polls.
Also replaced bare `except Exception` with `except httpx.HTTPError` per CLAUDE.md rules.

## Verification

- `grep "TTLCache" api/main.py` → 2 matches (import + instantiation) ✓
- `grep "range(120)" api/main.py` → 0 matches ✓
- `grep "poll_interval" api/main.py` → 6 matches ✓
- `grep "cachetools" requirements.txt` → 1 match ✓
- `python -c "from api.main import app; print('import OK')"` → import OK ✓

## Deviations from Plan

### Plan step mismatch (no-op, not a bug)

Plan Task 1 step 6 referenced wrapping standalone `/api/oathnet/breach`, `/api/oathnet/stealer`, `/api/oathnet/holehe`, `/api/oathnet/ip` endpoint handlers. These endpoints do not exist in the codebase — OathNet is exclusively called via `_stream_search`. No action taken; this was likely written against a future or alternative endpoint structure.

### Pre-existing `except Exception` in SpiderFoot ping block

Line ~1314: `except Exception:` in the SpiderFoot ping connectivity check is pre-existing code outside the polling loop scope of this task. Per CLAUDE.md scope rules, pre-existing issues in adjacent code are deferred.

**Deferred:** Fix ping block `except Exception` → `except (httpx.ConnectError, httpx.TimeoutException)`.

## Known Stubs

None — all cache wrapping wires to live API calls, no stubs or placeholders.

## Self-Check: PASSED

Files verified:
- FOUND: api/main.py (modified with TTLCache + backoff)
- FOUND: requirements.txt (cachetools==5.5.0 added)

Commits verified:
- FOUND: d56e0ca — feat(11-04): add TTL response cache for external API calls
- FOUND: 448267c — feat(11-04): replace SpiderFoot fixed polling with exponential backoff
