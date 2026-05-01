---
phase: 16-sherlock-false-positive-filter-thordata-proxy-integration
plan: 02
status: complete
completed_at: "2026-05-01T01:34:59Z"
commit: 935fff05e6dbfe1690c45b371add61de5eb69cb2
---

# Plan 16-02 Summary — Sherlock Engine Rewrite

## What Shipped

### Public API changes (consumed by Plan 03 + Plan 04)
- `PlatformResult` gains `confidence: int = 0` and `state: str = "not_found"` fields; `found: bool` is now a computed shim (`state != "not_found"`)
- `SherlockResult` gains `likely: list[PlatformResult]` and `proxy_used: bool` fields
- `PLATFORMS` dict entries gain `negative_markers: list[str]` (25 platforms populated from 16-RESEARCH.md table)

### Bug fixes shipped
- **Pitfall 1 (asyncio.TimeoutError dead-catch)**: replaced with `httpx.TimeoutException` — the dead branch is gone; timeouts now correctly surface as `error="timeout"` in PlatformResult
- **Pitfall 4 (cosmetic body cap)**: `resp.text[:cap]` replaced by `_fetch_with_cap()` using `client.stream()` + `aiter_bytes(8192)` — cap is enforced during download, not after

### New capabilities
- `_compute_confidence()` — pure function, 3-signal scoring (status=+40, text=+40, size=+20), negative_markers short-circuit to `(0, "not_found")`, threshold-based 3-state classifier
- `_fetch_with_cap()` — real streaming body cap via httpx; headers captured before body iteration (Cloudflare cf-mitigated detection, Pitfall 5)
- `_check_platform_with_retry()` — ProxyError → rotate sessid → proxy_unavailable on 2nd failure (D-06)
- Cloudflare `cf-mitigated: challenge` header detection → `error="cf_challenge"`, confidence=0
- `_build_sticky_url()` / `_build_rotate_url()` — Thordata sticky session helpers
- `_masked_proxy_log()` — returns `host:port` only, never `user:pass` (D-H5)
- `OutboundRateLimiter` — token bucket singleton at 1 req/s per domain (CLAUDE.md mandate, D-04)
- SHA256-truncated username audit log (D-H13) — plaintext username never logged

### Sesstime correction (Pitfall 2)
D-03 specified `sesstime-60` intending 60 seconds. Thordata docs unit is MINUTES. Implemented as `_STICKY_SESSTIME_MINUTES = 2` (2 minutes = 120s — covers full ~30s search plus 1x retry margin).

### search_username() result routing
- `confirmed` → `result.found`
- `likely` → `result.likely`
- error → `result.errors`
- else → `result.not_found`
- Budget: `_budget.record_usage(per_search_counter["bytes"])` called after gather

## Metrics
- `modules/sherlock_wrapper.py`: 745 LOC (up from ~293 pre-Phase-16)
- `tests/unit/test_sherlock_wrapper.py`: 415 LOC, 20 unit tests (Tasks 1+2)

## Security compliance
- D-H5: `_masked_proxy_log` used in all log lines touching proxy URL
- D-H13: SHA256 hash prefix only in audit log — raw username never logged
- CLAUDE.md exception ladder: `ProxyError` caught before `HTTPError`; no bare `except Exception` in `_check_platform`

## Next
Plan 03 — route wiring: SherlockUsernameRequest validator, budget circuit breaker, extended SSE serializer, /health Thordata metrics, lifespan proxy health check.
