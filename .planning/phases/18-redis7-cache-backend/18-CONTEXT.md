# Phase 18: Redis7 Cache Backend - Context

**Gathered:** 2026-05-08
**Status:** Ready for execution planning
**Source:** User request: "mudanca redis7 no lugar do TTLCache"

<domain>
## Phase Boundary

Replace current process-local search cache with Redis7:

1. Add Redis 7 service/config/dependency.
2. Add an async cache contract in `api/cache.py` with Redis backend and in-memory fallback.
3. Migrate `api/services/search_service.py` from sync `cachetools.TTLCache` helpers to async cache helpers.
4. Decouple `/health` from `_api_cache` and expose cache backend stats.

Out of scope:
- Redis as queue, session store, rate-limit backend, or database.
- Cache stampede coordination beyond single-key get/set.
- Caching full OathNet `raw_response` or nested dataclass `raw` payloads.
- Changing OathNet API behavior or response rendering.

Requirements covered: **CACHE-01..CACHE-10**.
</domain>

<decisions>
## Implementation Decisions

### Redis Runtime
- Use `redis:7-alpine`.
- Redis stays only on Compose `internal` network.
- No `ports:` mapping for Redis.
- Add `expose: ["6379"]`.
- Add healthcheck: `redis-cli ping`.
- Use memory ceiling: `--maxmemory 64mb --maxmemory-policy allkeys-lru`.
- Disable persistence for cache semantics: `--save "" --appendonly no`.
- Do not gate `nexus` startup on Redis health. Redis is optional cache infrastructure; if Redis is down and `CACHE_FAIL_OPEN=true`, FastAPI must still start and treat cache as miss-only.

### Env Contract
- `REDIS_URL=redis://redis:6379/0`
- `CACHE_TTL_SECONDS=300`
- `CACHE_KEY_PREFIX=nexus:v1:search`
- `CACHE_FAIL_OPEN=true`
- `CACHE_MAX_VALUE_BYTES=262144`

### Backend Contract
Create `api/cache.py`:
- `CacheBackend` protocol/base class.
- `RedisCacheBackend`.
- `InMemoryCacheBackend`.
- `CacheStats` dataclass.
- Module singleton `cache_backend`.
- Public async methods: `startup()`, `shutdown()`, `get(endpoint, query)`, `set(endpoint, query, value, ttl=None)`, `stats()`.

### Serialization
- Cache JSON-safe DTOs only.
- Breach/stealer cache values must round-trip via dataclass helpers, not pickle.
- Do not cache `raw_response`.
- Do not cache nested raw payload fields either (`BreachRecord.raw`, `StealerRecord.raw`, or any key named `raw`).
- Enforce `CACHE_MAX_VALUE_BYTES` before Redis write.

### Failure Policy
- Fail open for cache `get`/`set`: log warning, increment error counter, return miss / skip set.
- Startup should not crash or block app if `CACHE_FAIL_OPEN=true`.
- If `CACHE_FAIL_OPEN=false`, Redis startup failure may raise.

### Search-Service Migration
- `_get_cached` and `_set_cached` become async wrappers.
- All call sites in `_stream_search` use `await`.
- Remove `_api_cache` export entirely.
- `api/main.py` must stop importing `_api_cache`.
- `api/routes/health.py` imports cache stats from `api.cache`, not `api.services.search_service`.

### Claude's Discretion
- Exact Redis Python client version, but must support `redis.asyncio` on Python 3.12.
- Internal stat counter field names as long as `/health` exposes backend/reachable/hit/miss/error values.
- Test fake style: fake Redis class or in-memory backend, whichever keeps tests deterministic.
</decisions>

<canonical_refs>
## Canonical References

### Existing implementation
- `api/services/search_service.py` - current `_api_cache`, `_cache_key`, `_get_cached`, `_set_cached`, OathNet cache call sites.
- `api/routes/health.py` - current health/memory cache fields and direct `_api_cache` import.
- `api/main.py` - lifespan startup/shutdown and stale `_api_cache` import.
- `docker-compose.yml` - current `nexus`, `nginx`, `certbot`, `internal` network.
- `requirements.txt` - current `cachetools==5.5.0`.
- `modules/oathnet_client.py` - OathNet dataclasses that require DTO serialization helpers.

### Planning references
- `.planning/REQUIREMENTS.md` - CACHE-01..CACHE-10.
- `.planning/ROADMAP.md` - Phase 18 goal and plan split.
- `PROPOSTA_MELHORIAS_API_PERFORMANCE.md` - cache critique: current TTLCache is too simple for richer search.
</canonical_refs>

<specifics>
## Specific Ideas

### Cache Key
Use stable key format:

`{CACHE_KEY_PREFIX}:{endpoint}:{sha256(normalized_query).hexdigest()}`

Keep normalized query as `query.lower().strip()`.

### DTO Helpers
Add helper functions in `api/services/search_service.py` or `api/cache.py`:
- `oathnet_result_to_cache(result: OathnetResult, include_breaches=True, include_stealers=True) -> dict`
- `oathnet_result_from_cache(data: dict) -> OathnetResult`

Use `dataclasses.asdict()` for known dataclasses, then drop `raw_response` and exact `raw` keys recursively.

### Health Shape
`/health` should include:

```json
"cache": {
  "backend": "redis",
  "reachable": true,
  "hits": 1,
  "misses": 2,
  "errors": 0,
  "entries": null
}
```

Keep legacy `cache_entries` as integer if cheap/available; otherwise set `0` or remove only if tests/docs are updated in the same plan.
</specifics>

<deferred>
## Deferred Ideas

- Redis-backed slowapi/rate-limit storage.
- Cache stampede lock (`SET NX`).
- Per-endpoint TTL policy beyond 300 seconds.
- Prometheus metrics exporter.
- Redis persistence/AOF.
</deferred>

---

*Phase: 18-redis7-cache-backend*
*Context locked: 2026-05-08*
