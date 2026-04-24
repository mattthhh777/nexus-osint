---
phase: 15-refactor-main-py-layers
plan: 02
status: complete
completed: 2026-04-24
commits:
  - bce9d7c feat(15-02): create api/deps.py — extract auth dependency providers
  - a6f6f19 feat(15-02): remove auth deps from api/main.py, re-import from api.deps
---

# Phase 15 Plan 02 — SUMMARY

## What Was Done

Extracted 6 symbols from `api/main.py` to new `api/deps.py`:
- `security` (HTTPBearer instance)
- `_last_blacklist_warn` (rate-limit warn state)
- `get_client_ip` (IP extraction with Cloudflare trust chain)
- `_decode_token` (JWT decode — added to scope because get_current_user depends on it)
- `_check_blacklist` (async DB lookup, fail-closed on error)
- `get_current_user` (FastAPI Depends provider)
- `get_admin_user` (FastAPI Depends provider)

`api/main.py` now re-imports all 6 via `from api.deps import (...)`.
`tests/unit/test_security_gates.py` updated to monkeypatch `api.deps._db` in addition to `api.main._db` for the `_check_blacklist` test.

## Gate Results

- pytest: 61 passed, 1 failed (pre-existing `test_full_nexus_flow`) ✅
- `python -c "import api.main"` → no circular import ✅
- `from api.main import` count in tests: 6 (≤ baseline 6) ✅
- `api/deps.py` has all 6 symbols ✅
- `api/main.py` has zero definitions of those 6 symbols ✅

## Deviations

- `_decode_token` added to scope (not in original CONTEXT.md D-03) — necessary to avoid circular import since `get_current_user` calls it directly.
- Docker smoke skipped — Docker Desktop offline on Windows (expected deviation, noted in PLAN.md).
- `_create_token` and `_revoke_token` remain in main.py — only called by route handlers, deferred to Plan 04.

## Next

Plan 03 (or Plan 2.5): introduce `app.state.db/orchestrator` in lifespan + create `get_db()/get_orchestrator()` in deps.py. Decouples services from module-global singletons, enables `app.dependency_overrides` in integration tests.
