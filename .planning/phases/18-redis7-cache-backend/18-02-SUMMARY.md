# 18-02 Summary - Redis Search Cache Migration + Health Stats

## Objective

Move actual search cache behavior from `cachetools.TTLCache` to the async cache backend, expose cache health stats, and remove the old dependency.

## Files Changed

- `api/services/search_service.py`: removed `TTLCache`/`_api_cache`; added OathNet DTO helpers; migrated all cache reads/writes to `await cache_backend.get/set`; strips `raw_response` and nested `raw` payloads.
- `api/routes/health.py`: decoupled health from search internals; added `cache` stats object and kept legacy `cache_entries`.
- `api/main.py`: removed stale `_api_cache` import.
- `requirements.txt`: removed `cachetools`.
- `tests/test_search_cache_redis.py`: added DTO round-trip and duplicate upstream call avoidance tests.
- `tests/test_health.py`: added cache stats/decoupling tests.

## Verification

- `pytest tests/test_cache_backend.py tests/test_search_cache_redis.py tests/test_health.py -q` -> `9 passed`
- `python -m compileall api` -> passed
- `rg -n "TTLCache|cachetools|_api_cache" api requirements.txt` -> no matches
- `rg -n "redis:7-alpine|CACHE_TTL_SECONDS|cache_backend" docker-compose.yml api .env.example requirements.txt` -> expected Redis/cache wiring found

## Deviations from Plan

- No commit created because worktree already had unrelated and overlapping uncommitted changes in phase/code files. Avoided staging user/previous-session changes.
- Redis smoke with a live container was not run in this local execution. Coverage uses fake Redis and in-memory backend tests.

## Outcome

CACHE-04, CACHE-05, CACHE-07, CACHE-09, and CACHE-10 are satisfied. Redis outage cannot turn a search into HTTP 500 through cache code when `CACHE_FAIL_OPEN=true`.
