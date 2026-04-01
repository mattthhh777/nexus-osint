---
phase: 11-cost-optimization
plan: 01
status: complete
completed: "2026-04-01"
commits:
  - 2612b83  # test(11-01): failing tests for async OathnetClient
  - 2f2b3eb  # feat(11-01): rewrite OathnetClient as async httpx.AsyncClient singleton
  - 364edcb  # feat(11-01): replace per-request OathnetClient with singleton in main.py
requirements_met:
  - COST-01
  - COST-02
  - COST-05
---

# Plan 11-01 Summary — Async OathnetClient Singleton

## What Was Done

Migrated `modules/oathnet_client.py` from sync `requests` library to async `httpx.AsyncClient` and converted from per-request instantiation to a module-level singleton.

## Changes

**modules/oathnet_client.py**
- Replaced `requests.Session` with `httpx.AsyncClient` (persistent TCP/TLS pool)
- All 15 methods converted from sync to async (no `asyncio.to_thread` needed)
- Specific error handling: `httpx.ConnectError`, `TimeoutException`, `HTTPStatusError`
- Module-level singleton `oathnet_client` exported for use in main.py
- `async close()` method for graceful shutdown

**api/main.py**
- Removed all 5 `OathnetClient(api_key=...)` per-request instantiations
- Imported `oathnet_client` singleton once at module level
- Removed all `asyncio.to_thread(client.*)` wrappers
- Null-guard at `_stream_search` entry point
- FastAPI shutdown handler calls `await oathnet_client.close()`

**tests/test_oathnet_client.py**
- 7 tests: init, search_breach, search_stealer_v2, singleton, HTTPStatusError, ConnectError, close
- All pass with respx mocks (no real network calls)

## Verification

- `grep "OathnetClient(api_key=" api/main.py` → 0 matches ✓
- `grep "import requests" modules/oathnet_client.py` → 0 matches ✓
- `grep "httpx.AsyncClient" modules/oathnet_client.py` → 1 match ✓
- `pytest tests/test_oathnet_client.py -x` → 7 passed ✓

## Impact

Eliminates 5 redundant TCP/TLS handshakes per search request and removes thread pool overhead from `asyncio.to_thread` wrapping.
