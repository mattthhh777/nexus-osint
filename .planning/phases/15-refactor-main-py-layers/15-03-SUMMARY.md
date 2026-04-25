---
phase: 15-refactor-main-py-layers
plan: 03
status: COMPLETE
completed_at: "2026-04-25T03:00:00-03:00"
---

# Plan 03 Summary — Services Extraction

## Outcome

All business-logic helpers evacuated from `api/main.py` into 3 service modules + 1 config module.
Route handlers still work via re-imports. Test suite: 61 passed / 1 pre-existing failure.

## File Footprints

| File | Lines | Notes |
|------|------:|-------|
| `api/config.py` | 77 | Leaf module — zero internal imports |
| `api/services/__init__.py` | 1 | Package marker |
| `api/services/auth_service.py` | ~140 | 9 functions + module state |
| `api/services/search_service.py` | ~720 | 12 functions incl. 510-line SSE generator |
| `api/services/admin_service.py` | 14 | `_validate_id` only |
| `api/deps.py` | -6 lines | JWT constants now from api.config |
| `api/main.py` | 752 (was 1635) | -883 lines, routes-only |

## Lines Removed from api/main.py

Pre-edit: 1635 lines → Post-edit: 752 lines (-883 lines)

Blocks removed:
- Config constants block (env vars, JWT, rate limits, paths, memory thresholds, timeouts)
- `_validate_jwt_secret`, `_load_users`, `_save_users`, `_safe_hash`, `_safe_verify`, `_ensure_default_user`, `_verify_user`
- `_create_token`, `_revoke_token`
- `_api_cache` setup + `_cache_key`, `_get_cached`, `_set_cached`
- `_save_quota`, `_log_search`
- `detect_type`, `MODULE_TIMEOUTS`, `with_timeout`
- `MAX_BREACH_SERIALIZE`, `_seen_breach_extra_keys`, `_serialize_breaches`, `_serialize_stealers`
- `_stream_search` (510 lines)
- `_run_spiderfoot`, `_parse_discord_history`
- `_validate_id`
- `_ALLOWED_ORIGINS` definition

Imports removed from main.py: `hashlib`, `json`, `sys`, `uuid`, `timedelta`, `AsyncGenerator`, `Union`,
`bcrypt`, `ipaddress`, `TTLCache`, `RedirectResponse`, `SpiderFootTarget`

## pytest Result

```
1 failed, 61 passed in 5.25s
```
Pre-existing: `test_full_nexus_flow` (auth-gate scenario, out-of-scope since Plan 01).

## Import Chain

```
python -c "import api.main; import api.deps; ..."  → ALL OK
python -c "from api.main import app; from api.deps import get_current_user; ..."  → OK
```

No circular imports.

## _stream_search Transplant

Body: 510 lines (>450 requirement). `from modules.sherlock_wrapper import search_username` preserved inside function body.

## from api.main import baseline

Before Plan 03: 6 | After: 6 (unchanged, <= baseline requirement)

## Deviations

- **Docker smoke**: Docker Desktop unavailable on Windows — same as Plans 01 and 02. Accepted.
- **Test fixes**: 3 test files updated to patch `api.services.auth_service` instead of `api.main` for `_users_cache`/`USERS_FILE`. Root cause: `_load_users` reads from auth_service's namespace. Additionally, `_validate_jwt_secret` restored to read from `os.environ.get("JWT_SECRET", "")` at call time (not module-level) to preserve test monkeypatching behavior.
- **D-03-03 (_seen_breach_extra_keys runtime check)**: Deferred to manual smoke — requires a real OathNet query in Docker environment. Pattern confirmed safe (shared set reference, not binding).

## Commit SHAs

| Task | SHA | Message |
|------|-----|---------|
| 1 | 9c15e40 | feat(15-03): create api/config.py — extract constants and env vars |
| 2 | a7da9e9 | feat(15-03): create api/services/auth_service.py — auth business logic |
| 3 | d83efa3 | feat(15-03): create api/services/search_service.py — search business logic + SSE generator |
| 4 | c07cdf0 | feat(15-03): create api/services/admin_service.py — _validate_id guard |
| 5 | a548bac | refactor(15-03): consolidate api/deps.py JWT reads via api.config |
| 6 | 685f12c | feat(15-03): evacuate business logic from api/main.py, re-import from services and config |
