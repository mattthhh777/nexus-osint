# 18-01 Summary - Redis Runtime + Async Cache Backend

## Objective

Add Redis7 runtime/config and a reusable async cache backend without changing search behavior yet.

## Files Changed

- `docker-compose.yml`: added private `redis:7-alpine` service, no public port, bounded memory command, healthcheck, `redis_data` named volume, and cache env vars for `nexus`.
- `.env.example`: documented Redis/cache env contract.
- `requirements.txt`: added `redis==5.1.1`.
- `api/config.py`: added Redis/cache config constants and boolean parser.
- `api/cache.py`: added async cache contract, `RedisCacheBackend`, `InMemoryCacheBackend`, fail-open behavior, key hashing, size guard, stats.
- `api/main.py`: wired cache startup/shutdown into lifespan.
- `tests/test_cache_backend.py`: added backend/fail-open/stat tests.

## Verification

- `pytest tests/test_cache_backend.py -q` -> `5 passed`
- `rg -n "redis:7-alpine|nexus-redis|REDIS_URL|CACHE_TTL_SECONDS|CACHE_FAIL_OPEN|CACHE_MAX_VALUE_BYTES" docker-compose.yml .env.example requirements.txt api/config.py`

## Deviations from Plan

- No commit created because worktree already had unrelated and overlapping uncommitted changes in phase/code files. Avoided staging user/previous-session changes.

## Notes

- `cachetools` intentionally remained until 18-02.
- Redis does not gate `nexus` startup; cache is fail-open infrastructure.
