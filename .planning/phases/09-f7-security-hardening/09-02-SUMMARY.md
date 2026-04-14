---
phase: 09-f7-security-hardening
plan: 02
status: complete
completed_at: "2026-04-07"
files_modified:
  - requirements.txt
  - api/main.py
  - tests/integration/test_rate_limiting.py
  - tests/integration/__init__.py
tests_added: 7
tests_passing: 35
---

# Plan 09-02 Summary — Wave 2: slowapi Rate Limiting

## What Was Done

### Task 1: slowapi Installation + Limiter Wiring
- Added `slowapi==0.1.9` to `requirements.txt`
- Added imports: `Limiter`, `RateLimitExceeded`, `get_remote_address`
- Added 6 env-tunable RL_* constants near `MAX_USERS`:
  - `RL_LOGIN_LIMIT=5/minute`, `RL_REGISTER_LIMIT=3/hour`, `RL_SEARCH_LIMIT=10/minute`
  - `RL_SPIDERFOOT_LIMIT=3/hour`, `RL_ADMIN_LIMIT=30/minute`, `RL_READ_LIMIT=60/minute`
- Implemented `_rate_key(request)`: prefers JWT `sub` claim from `nx_session` cookie, falls back to client IP
- Instantiated `Limiter(key_func=_rate_key, storage_uri="memory://")` and wired to `app.state.limiter`
- Implemented custom `_rate_limit_handler` with explicit `Retry-After` header (avoids `_inject_headers` bug with dict-returning endpoints)

### Task 2: Endpoint Decoration + _check_rate Removal
- Applied `@limiter.limit(...)` to **18 endpoints**:
  - Auth: `/api/auth`, `/api/login`, `/api/logout`, `/api/me`
  - Search: `/api/search`, `/api/search/more-breaches`
  - Admin: `/api/admin/auth-gate`, `/api/admin/stats`, `/api/admin/logs`, `/api/admin/users` (GET/POST), `/api/admin/users/{username}` (DELETE)
  - Victims: `/api/victims/search`, `/api/victims/{log_id}/manifest`, `/api/victims/{log_id}/files/{file_id}`
  - SpiderFoot: `/api/spiderfoot/status`
  - Health: `/health`, `/health/memory`
- Added `request: Request` parameter to endpoints that lacked it (required by slowapi)
- **Deleted `_check_rate` function entirely** (FIND-04 superseded — zero callers remaining)
- Removed `_check_rate` call inside `/api/login` handler (FIND-12)

### Tests Created
`tests/integration/test_rate_limiting.py` — 7 tests:
1. `test_login_429_after_five_attempts` — 6th login = 429
2. `test_login_429_has_retry_after` — Retry-After header present on 429
3. `test_login_no_check_rate_db_writes` — `_check_rate` gone; no rate_limits DB writes
4. `test_search_429_after_ten_requests` — 11th search = 429
5. `test_search_per_user_isolation` — user A limit ≠ user B limit (per-JWT-sub keying)
6. `test_search_429_has_retry_after` — Retry-After on search 429
7. `test_admin_create_user_429_after_register_limit` — 4th create = 429

## Key Decisions
- `headers_enabled=False` (default) on Limiter: slowapi's `_inject_headers` fails when endpoints return dicts instead of Response objects. Custom `_rate_limit_handler` adds `Retry-After` explicitly only on 429 path.
- `storage_uri="memory://"`: in-memory counters reset on container restart. Acceptable for single-instance VPS — no Redis dependency.
- `_check_rate` deleted (not just disabled): SQLite-based rate limiting superseded entirely by slowapi.

## Verification
- `pytest tests/integration/test_rate_limiting.py` → 7/7 PASS
- `pytest tests/unit/test_security_gates.py` → 14/14 PASS (no regression)
- `grep -n "_check_rate" api/main.py` → zero callable references (function deleted)
- `grep -c "@limiter.limit" api/main.py` → 18 matches

## Next
Wave 3: Frontend CSP Preparation — purge 73 `onclick` handlers (Plan 09-03)
