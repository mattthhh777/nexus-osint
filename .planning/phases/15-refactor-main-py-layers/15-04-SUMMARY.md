---
phase: 15-refactor-main-py-layers
plan: 04
status: complete
completed_at: "2026-04-26"
commits:
  - f3a381c  # Task 1: get_db + get_orchestrator_dep in api/deps.py
  - c5831c0  # Task 2: D-05 service signatures
  - 114d94d  # Task 3: wire app.state.db/orchestrator + pass db/orch in main.py
  - 14a1aaf  # Task 4: api/routes/root.py
  - b319907  # Task 5: api/routes/auth.py
  - 124300e  # Task 6: api/routes/admin.py
  - 0a25f93  # Task 7: api/routes/search.py
  - 5811a9f  # Task 8: api/routes/victims.py + spiderfoot.py + health.py
---

## What was done

Block-moved every `@app.*` route handler from `api/main.py` into 7 `api/routes/*.py`
modules and implemented the D-05 service-signature contract.

### Tasks 4–8 — route extraction (atomic commits, tests green after each)

| Task | Module | Routes |
|------|--------|--------|
| 4 | api/routes/root.py | GET /, HEAD /, GET /admin |
| 5 | api/routes/auth.py | /api/auth, /api/login, /api/me, /api/logout, /api/admin/auth-gate |
| 6 | api/routes/admin.py | /api/admin/stats, /api/admin/logs, /api/admin/users CRUD |
| 7 | api/routes/search.py | /api/search (SSE), /api/search/more-breaches, /api/admin/breach-extra-keys |
| 8 | api/routes/victims.py | /api/victims/* (3 endpoints) |
| 8 | api/routes/spiderfoot.py | /api/spiderfoot/status |
| 8 | api/routes/health.py | /health (GET+HEAD), /health/memory |

### Task 9 — verification gate results

- `python -c 'import api.main'` → exit 0 (no circular imports)
- `wc -l api/main.py` → 234 (< 250 target)
- Zero `@app.<verb>` decorators in main.py (only docstring mention)
- 7 `app.include_router(...)` calls present
- `grep -rc 'from api.main import' tests/` → 6 (≤ Plan 03 baseline)
- pytest: **61 passed / 1 pre-existing failure** (test_full_nexus_flow)

## Test fixes required during this plan

Search rate-limit tests (3) needed `get_db` + `get_orchestrator_dep` overrides —
routes now use `Depends(...)` instead of module-level singletons; `app.state` not
initialised in test env. Pattern:
```python
m.app.dependency_overrides[_get_db] = lambda: MagicMock()
m.app.dependency_overrides[_get_orch] = lambda: _mock_orch  # DegradationMode.NORMAL
```

`test_health_endpoint` needed same pattern for `get_orchestrator_dep`.

Admin tests (2) needed additional patch on `api.routes.admin.MAX_USERS` (D-04-02).

## Re-export shim in api/main.py (D-04-05)

Symbols kept at `api.main` namespace for test monkeypatches:
`_db`, `_create_token`, `_decode_token`, `JWT_SECRET`, `JWT_ALGORITHM`, `MAX_USERS`,
`limiter`, `app`.

## Out of scope

Plan 05 (if needed): trim api/main.py further once tests migrate imports to route/service modules directly.
