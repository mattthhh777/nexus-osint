---
phase: 11-cost-optimization
plan: "02"
subsystem: infra
tags: [httpx, aiohttp, requests, dependencies, http-client, sherlock, python]

# Dependency graph
requires:
  - phase: 11-cost-optimization/11-01
    provides: oathnet_client migrated from requests to httpx (oathnet_client.py)
provides:
  - sherlock_wrapper.py using httpx.AsyncClient exclusively
  - requirements.txt with single HTTP library (httpx==0.27.2)
  - aiohttp and requests fully removed from codebase and dependencies
affects: [docker-build, pip-install, F5-docker-optimization, F6-stack-modernization]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "httpx.AsyncClient with timeout, follow_redirects, verify=False, limits — standard pattern for OSINT platform checks"
    - "httpx.Limits(max_connections=15) to cap parallel connections to external sites"
    - "Granular exception hierarchy: httpx.ConnectError > httpx.HTTPStatusError > httpx.HTTPError"

key-files:
  created: []
  modified:
    - modules/sherlock_wrapper.py
    - requirements.txt

key-decisions:
  - "httpx.Timeout(10.0, connect=5.0) replaces aiohttp.ClientTimeout — same semantics, one library"
  - "verify=False on AsyncClient mirrors aiohttp ssl=False — intentional for OSINT reachability checks against sites with self-signed certs"
  - "httpx.Limits(max_connections=15) replaces aiohttp.TCPConnector(limit=15) — caps parallel socket pool to match original constraint"
  - "resp.text is a sync property in httpx (not a coroutine) — removed await, no behavior change"

patterns-established:
  - "Platform: httpx.ConnectError catches DNS failures and TCP refused; httpx.HTTPStatusError catches 4xx/5xx when raise_for_status() is used"

requirements-completed: [COST-03]

# Metrics
duration: 2min
completed: "2026-04-01"
---

# Phase 11 Plan 02: HTTP Library Consolidation Summary

**Migrated sherlock_wrapper.py from aiohttp to httpx.AsyncClient and removed aiohttp + requests from requirements.txt, leaving httpx as sole HTTP client (~15MB pip reduction)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-01T19:53:29Z
- **Completed:** 2026-04-01T19:55:29Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- Replaced `aiohttp.ClientSession` + `aiohttp.TCPConnector` with `httpx.AsyncClient` (timeout, follow_redirects, verify=False, limits)
- Updated all aiohttp API surface: `resp.status` -> `resp.status_code`, `await resp.text()` -> `resp.text` (sync property), timeout/connector constructors
- Replaced `aiohttp.ClientSSLError` / `aiohttp.ClientConnectorError` with `httpx.ConnectError` + `httpx.HTTPStatusError` + `httpx.HTTPError`
- Removed `import aiohttp` and `import requests` (the latter was already unused) from sherlock_wrapper.py
- Removed `aiohttp==3.10.5` and `requests==2.32.3` from requirements.txt — zero remaining usages confirmed by project-wide grep

## Task Commits

1. **Task 1: Migrate sherlock_wrapper from aiohttp to httpx.AsyncClient** - `cf4a2f2` (feat)
2. **Task 2: Remove aiohttp and requests from requirements.txt** - `9aa97ae` (chore)

## Files Created/Modified

- `modules/sherlock_wrapper.py` - aiohttp removed, httpx.AsyncClient introduced with equivalent connection limits and timeout semantics
- `requirements.txt` - aiohttp==3.10.5 and requests==2.32.3 removed; httpx==0.27.2 is now sole HTTP client

## Decisions Made

- `verify=False` retained on `httpx.AsyncClient` — mirrors the original `ssl=False` in aiohttp connector. OSINT platform checks intentionally allow self-signed certs to maximize reachability signal. This is an OSINT-domain choice, not a mistake.
- `httpx.Limits(max_connections=15)` preserves the original `aiohttp.TCPConnector(limit=15)` cap — prevents socket exhaustion on the 1GB VPS during the 25-platform parallel check.
- Granular exception mapping chosen over broad catch: `httpx.ConnectError` (DNS/TCP), `httpx.HTTPStatusError` (4xx/5xx), `httpx.HTTPError` (all other httpx errors). This is narrower than the original aiohttp catch and gives better error categorization.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All acceptance criteria passed on first attempt. Project-wide grep confirmed zero remaining aiohttp/requests imports after migration.

## User Setup Required

None - no external service configuration required. Dependency change takes effect on next `pip install -r requirements.txt` or Docker rebuild.

## Next Phase Readiness

- HTTP library is now consolidated to httpx==0.27.2 across the entire codebase
- aiohttp and requests are safe to uninstall from any dev environment: `pip uninstall aiohttp requests`
- Docker image size will decrease ~15MB on next build (aiohttp has heavy C extensions)
- Ready for Plan 11-03 (next cost optimization task)

---
*Phase: 11-cost-optimization*
*Completed: 2026-04-01*
