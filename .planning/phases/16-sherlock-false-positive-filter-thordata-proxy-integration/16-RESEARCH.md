# Phase 16: Sherlock False-Positive Filter + Thordata Proxy Integration - Research

**Researched:** 2026-04-29
**Domain:** httpx proxy routing, residential proxy sticky sessions, multi-signal confidence scoring, Pydantic v2 validation, in-memory budget tracking
**Confidence:** HIGH (stack verified against installed packages; Thordata docs fetched from official source; httpx API confirmed via runtime introspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Proxy Scope**
- D-01: Proxy applied ONLY to `modules/sherlock_wrapper.py`. OathNet and SpiderFoot bypass proxy entirely.

**Proxy Session Strategy**
- D-02: Hybrid session — sticky per `search_id`, rotate only on retry after 4xx/429/timeout/proxy error.
- D-03: Sticky session TTL = 60 seconds via username suffix `-sessid-<search_id>-sesstime-60`. (NOTE: Research found Thordata sesstime is in MINUTES — see Open Questions #2 and Pitfall 2.)
- D-04: Per-domain outbound rate limit = 1 req/s per domain.
- D-05: `httpx.AsyncClient` `max_connections=8` when proxy active.

**Proxy Fallback**
- D-06: On proxy failure: retry 1x (forces IP rotation). On second failure -> `error: proxy_unavailable`. No direct (proxy-bypass) fallback.
- D-07: Startup `HEAD https://api.ipify.org` through proxy in FastAPI lifespan. Non-blocking.

**False-Positive Filter**
- D-08: Multi-signal confidence score 0-100: status_code match +40, text marker match +40, size sanity >3KB +20.
- D-09: Per-platform `negative_markers` -- strings that REJECT even if positive claim_value hits. Confidence dropped to 0 on match.
- D-10: Thresholds: score >= 70 -> `confirmed`; 40-69 -> `likely`; < 40 -> `not_found`.
- D-11: Thresholds tunable via `SHERLOCK_CONFIRMED_THRESHOLD` (70) and `SHERLOCK_LIKELY_THRESHOLD` (40).
- D-12: Existing 3 claim_types preserved -- only `negative_markers` added to PLATFORMS dict.

**Result Confidence Display**
- D-13: 3-state output: `confirmed` (full card, amber), `likely` (muted + "Unverified" badge), `not_found` (not rendered).
- D-14: API response includes `state` and `confidence: int`. Frontend consumes `state` only -- never recomputes.

**Cost / Budget Controls**
- D-15: 512KB global cap preserved. Sherlock-specific: 256KB per response.
- D-16: In-memory daily budget counter `_thordata_bytes_today` + `_thordata_requests_today`, reset at 00:00 UTC. SOFT 500MB -> WARNING. HARD 1GB -> 503 + `Retry-After: 86400`.
- D-17: Per-search byte cap = 1MB total. Exceeded -> abort remaining platforms + partial result + log INFO.
- D-18: `THORDATA_DAILY_BUDGET_MB` (default 1024), `THORDATA_PER_SEARCH_CAP_MB` (default 1).
- D-19: New `/health` admin fields: `thordata.bytes_today_mb`, `thordata.requests_today`, `thordata.budget_remaining_pct`, `thordata.proxy_active: bool`.

**Security Hardening (D-H1 through D-H15)**
- D-H1: Thresholds applied exclusively backend. Frontend receives pre-classified `state` only.
- D-H2: Raw signal scores (status_pts/text_pts/size_pts) NOT exposed to frontend.
- D-H3: `negative_markers` never serialized in API response.
- D-H4: Budget/rate-limit decisions entirely backend -- no header/param can bypass.
- D-H5: `THORDATA_PROXY_URL` read via `api/config.py`; log `host:port` only, never `user:pass`.
- D-H6: Proxy errors surfaced as generic `"upstream_unavailable"`. Full exception goes to internal log only.
- D-H7: Add `THORDATA_PROXY_URL=http://USER:PASS@HOST:PORT` placeholder to `.env.example`.
- D-H8: Pydantic validator on `username`: regex `^[A-Za-z0-9_.\-]{1,64}$`.
- D-H9: Reject `/`, `:`, `?`, `#`, `&`, `=`, whitespace, null byte. Return 400, no echo of input.
- D-H10: Audit `claim_value` in PLATFORMS -- static literals only, never user input.
- D-H11: `RL_SEARCH_LIMIT=10/minute` per user retained. Sherlock concurrency bounded by global `Semaphore(5)`.
- D-H12: Budget circuit breaker returns explicit 503 + `Retry-After`. No silent drop.
- D-H13: Per-search log line: `username_hash` (SHA256 truncated 8 chars), `bytes_consumed`, `proxy_used: bool`, `confirmed_count`, `likely_count`, `errors_count`. Username plaintext NEVER logged.
- D-H14: `/health` Thordata metrics admin-gated via `Depends(get_admin_user)`.
- D-H15: Exception handling per CLAUDE.md per-layer pattern -- no bare `except Exception` in `_check_platform`.

### Claude's Discretion
- Internal naming of helper functions / private constants in `sherlock_wrapper.py`.
- Whether to extract budget tracker into `api/budget.py` or inline in `sherlock_wrapper.py`.
- Exact format of `/health` Thordata payload (nested vs flat) -- consistent with existing style.
- Specific `negative_markers` strings per platform.
- Whether to use Thordata sticky session via username syntax or separate session endpoint.

### Deferred Ideas (OUT OF SCOPE)
- Migrate to upstream Sherlock `data.json` (300+ platforms).
- Persistent Thordata budget across restarts.
- Per-platform proxy bypass list.
- CLI fallback through proxy.
- WebSocket/SSE live progress.
- ML-trained confidence model.
</user_constraints>

---

## Summary

Phase 16 modifies a single module (`modules/sherlock_wrapper.py`) with two orthogonal concerns: (1) routing all outbound HTTP through a Thordata residential rotating proxy to bypass DigitalOcean IP blocks on LinkedIn/Instagram/TikTok, and (2) replacing the existing binary found/not-found result with a 3-state multi-signal confidence score. Both changes are well-contained -- no new dependencies are needed (httpx 0.27.2 already supports `proxy=` natively), and the confidence scoring is pure Python logic layered over the existing `_check_platform` function.

The most important architectural insight is that the existing `sherlock_wrapper.py` has **two correctness bugs** that Phase 16 must fix: (1) it catches `asyncio.TimeoutError` but httpx raises `httpx.TimeoutException` -- these are entirely separate exception classes and the current `asyncio.TimeoutError` catch is dead code for HTTP timeouts; (2) `resp.text[:MAX_BODY_BYTES]` reads the full response body into memory before slicing -- the body cap is cosmetic, not real. Both must be fixed as part of this phase.

The daily budget tracker recommendation is **`api/budget.py` as a standalone module** rather than inline globals in `sherlock_wrapper.py`. Budget state is accessed by both `sherlock_wrapper.py` (write/enforce) and `api/routes/health.py` (read/expose). A dedicated `api/budget.py` with module-level state avoids circular import risk and enables isolated unit testing.

**Primary recommendation:** Use `httpx.AsyncClient(proxy=THORDATA_PROXY_URL, ...)` with `proxy=` singular. Build confidence scoring as a pure function `_compute_confidence(status, body, bytes_read, platform) -> tuple[int, str]`. Implement UTC midnight reset as a lazy check on next request rather than a background task.

---

## Standard Stack

### Core (all already installed -- zero new dependencies)

| Library | Installed Version | Purpose in Phase 16 | Notes |
|---------|------------------|---------------------|-------|
| httpx | 0.27.2 | Proxy routing, async HTTP to 25 platforms | `proxy=` param native; `httpx.ProxyError` available |
| pydantic | 2.8.2 | Username validator pattern (existing `SearchRequest` pattern) | `@field_validator` + `@classmethod` as in schemas.py |
| loguru | project-wide | Budget WARNING/CRITICAL, per-search audit log with hash | Already used across api/ |
| stdlib `hashlib` | 3.12 built-in | SHA256 username hash for logs (D-H13) | `hashlib.sha256(u.encode()).hexdigest()[:8]` |
| stdlib `urllib.parse` | 3.12 built-in | Extract `host:port` from `THORDATA_PROXY_URL` for log masking | `urlparse(url).hostname + ":" + str(port)` |
| stdlib `datetime` + `timezone` | 3.12 built-in | UTC day sentinel for daily budget reset | `datetime.now(timezone.utc).date()` |
| stdlib `secrets` | 3.12 built-in | Generate `search_id` for sticky session sessid | `secrets.token_hex(8)` = 16-char hex alphanumeric |

### No New Dependencies Required

Zero new packages added to `requirements.txt`. The entire implementation uses existing httpx 0.27.2 `proxy=` parameter, existing pydantic v2 field_validator pattern, and existing respx 0.22.0 for tests.

**Versions confirmed against installed packages:** httpx `0.27.2`, pydantic `2.8.2`, respx `0.22.0`, pytest-asyncio `1.3.0`.

---

## Architecture Patterns

### Recommended Project Structure Changes

```
modules/
└── sherlock_wrapper.py     <- MODIFIED: proxy injection, confidence scoring, body cap fix,
                               asyncio.TimeoutError bug fix, negative_markers in PLATFORMS

api/
├── budget.py               <- NEW: daily budget tracker (module-level state)
├── config.py               <- MODIFIED: 6 new env vars
├── routes/
│   ├── health.py           <- MODIFIED: /health/thordata admin endpoint
│   └── search.py           <- MODIFIED: username validator + budget circuit breaker
├── schemas.py              <- NO CHANGE (leaf module constraint, Phase 15 D-01)
└── services/
    └── search_service.py   <- MODIFIED: consume SherlockResult.likely + state/confidence fields

static/js/
└── render.js               <- MODIFIED: render 'likely' state with Unverified badge

.env.example                <- NEW: credential-free placeholder per D-H7
```

### Pattern 1: httpx Proxy Injection (httpx 0.27.2 Confirmed API)

**What:** Pass `proxy=` (singular) to `httpx.AsyncClient`. This is the current non-deprecated form in 0.27.x. The plural `proxies=` was deprecated in 0.26.0 and removed in 0.28.0 -- confirmed by runtime introspection of the installed 0.27.2 package.

**Confirmed via runtime:** `inspect.signature(httpx.AsyncClient.__init__)` shows both `proxy` and `proxies` parameters exist in 0.27.2. Use `proxy=` (singular) exclusively to be forward-compatible.

```python
# Source: httpx 0.27.2 AsyncClient.__init__ signature (confirmed via runtime introspection)
import httpx
from api.config import THORDATA_PROXY_URL  # str | None

def _build_client_kwargs(sticky_url: str | None) -> dict:
    """Build httpx.AsyncClient kwargs with optional Thordata sticky-session proxy."""
    base = {
        "headers": HEADERS,
        "timeout": CONNECT_TIMEOUT,
        "follow_redirects": True,
        "verify": False,
    }
    if sticky_url:
        base["proxy"] = sticky_url
        base["limits"] = httpx.Limits(max_connections=8, max_keepalive_connections=5)
    else:
        base["limits"] = httpx.Limits(max_connections=15, max_keepalive_connections=10)
    return base
```

### Pattern 2: Thordata Sticky Session URL Construction

**Confirmed facts from Thordata official docs (`doc.thordata.com`, fetched 2026-04-29):**

- Host: `t.pr.thordata.net`, Port: `9999`
- Full URL format: `http://td-customer-USERNAME:PASSWORD@t.pr.thordata.net:9999`
- Sticky session username format: `td-customer-USERNAME-sessid-STRING-sesstime-MINUTES`
- `sesstime` unit: **MINUTES** (not seconds). Range: 1-90 minutes.
- `sessid` accepts alphanumeric strings. No explicit character limit documented.
- Rotating session: omit `sessid`/`sesstime` entirely -- each request gets a new IP.
- Forced IP rotation on retry: use a DIFFERENT `sessid` value (new string = new IP pool assignment).

**CRITICAL UNIT CORRECTION (D-03):** D-03 specifies `sesstime-60` intending "60 seconds." Thordata uses MINUTES. `sesstime-60` = 60 minutes of IP lock -- wastes Thordata sticky pool. Correct value for covering a ~30s search + retry margin: `sesstime-2` (2 minutes = 120 seconds). The planner must document this correction and use `sesstime-2` in implementation.

```python
# Source: Thordata official docs (doc.thordata.com/doc/proxies/residential-proxies/making-request)
import urllib.parse
import re
import secrets

def _build_sticky_url(base_proxy_url: str, sessid: str) -> str:
    """
    Inject sticky session params into Thordata proxy URL username.

    Input:  http://td-customer-USER:PASS@t.pr.thordata.net:9999
    Output: http://td-customer-USER-sessid-abc123ef-sesstime-2:PASS@t.pr.thordata.net:9999

    sesstime=2 = 2 minutes (Thordata unit is MINUTES, minimum 1 minute).
    sessid is alphanumeric-only; strip any non-alnum chars for safety.
    """
    parsed = urllib.parse.urlparse(base_proxy_url)
    safe_sessid = re.sub(r"[^A-Za-z0-9]", "", sessid)[:16]
    new_username = f"{parsed.username}-sessid-{safe_sessid}-sesstime-2"
    new_netloc = f"{new_username}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))

def _build_rotate_url(base_proxy_url: str, sessid: str) -> str:
    """Build a rotation URL with a DIFFERENT sessid to force IP change on retry."""
    return _build_sticky_url(base_proxy_url, sessid + "r")  # appended 'r' = different IP pool

def _masked_proxy_log(proxy_url: str) -> str:
    """Return 'host:port' only -- never user:pass in logs (D-H5)."""
    parsed = urllib.parse.urlparse(proxy_url)
    return f"{parsed.hostname}:{parsed.port}"
```

**search_id source:** Generate internally in `search_username()` via `secrets.token_hex(8)` (16-char hex, safe alphanumeric). The caller does not need to supply this; it is a proxy implementation detail.

### Pattern 3: Confidence Scoring (Pure Function)

```python
# Source: CONTEXT.md D-08/D-09/D-10/D-12
_SCORE_STATUS   = 40
_SCORE_TEXT     = 40
_SCORE_SIZE     = 20
_MIN_BODY_BYTES = 3_072   # 3KB sanity threshold

def _compute_confidence(
    resp_status: int,
    resp_body: str,
    resp_body_bytes: int,
    platform: dict,
) -> tuple[int, str]:
    """
    Returns (confidence_score 0-100, state 'confirmed'|'likely'|'not_found').
    Negative markers short-circuit to (0, 'not_found') regardless of other signals.
    """
    from api.config import SHERLOCK_CONFIRMED_THRESHOLD, SHERLOCK_LIKELY_THRESHOLD
    body_lower = resp_body.lower()

    # Short-circuit: negative marker present -> not_found regardless of claim
    for marker in platform.get("negative_markers", []):
        if marker.lower() in body_lower:
            return 0, "not_found"

    score = 0
    claim_type  = platform["claim_type"]
    claim_value = platform["claim_value"]

    # Signal 1: status_code match (+40)
    if claim_type == "status_code":
        if resp_status == int(claim_value):
            score += _SCORE_STATUS
    else:
        if resp_status == 200:
            score += _SCORE_STATUS

    # Signal 2: text marker match (+40)
    if claim_type == "text_present":
        if str(claim_value).lower() in body_lower:
            score += _SCORE_TEXT
    elif claim_type == "text_absent":
        if str(claim_value).lower() not in body_lower:
            score += _SCORE_TEXT

    # Signal 3: size sanity (+20)
    if resp_body_bytes >= _MIN_BODY_BYTES:
        score += _SCORE_SIZE

    score = min(score, 100)

    if score >= SHERLOCK_CONFIRMED_THRESHOLD:
        state = "confirmed"
    elif score >= SHERLOCK_LIKELY_THRESHOLD:
        state = "likely"
    else:
        state = "not_found"

    return score, state
```

### Pattern 4: Body Cap Enforcement (Real Streaming Read)

**Critical finding:** The existing `resp.text[:MAX_BODY_BYTES]` is NOT a real body cap. `httpx.get()` reads the entire response body before `.text` is available; slicing the string afterward does not limit downloaded bytes. On large pages (Instagram, TikTok, LinkedIn can be 2-5MB), this wastes memory on the 1GB VPS.

**httpx 0.27.2 does NOT have a `max_response_size` constructor param.** The correct approach is `client.stream()` + `aiter_bytes()`:

```python
# Source: httpx official docs (python-httpx.org/advanced/proxies/) + confirmed available in 0.27.2
_SHERLOCK_BODY_CAP = 262_144  # 256KB per response (D-15)

async def _fetch_with_cap(
    client: httpx.AsyncClient,
    url: str,
    cap_bytes: int = _SHERLOCK_BODY_CAP,
) -> tuple[int, dict, bytes, int]:
    """
    Fetch URL, stopping body read at cap_bytes.
    Returns (status_code, response_headers, body_bytes, actual_bytes_read).
    Headers returned so caller can inspect cf-mitigated without re-fetching.
    """
    async with client.stream("GET", url) as resp:
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes(chunk_size=8192):
            chunks.append(chunk)
            total += len(chunk)
            if total >= cap_bytes:
                break
        body = b"".join(chunks)
        return resp.status_code, dict(resp.headers), body, total
```

Memory impact with real 256KB cap: 25 concurrent platforms x 256KB = ~6MB peak. Without real cap: 25 x 5MB (typical Instagram/TikTok page) = ~125MB peak per Sherlock search. The difference is material on a 1GB VPS.

### Pattern 5: Budget Tracker (`api/budget.py` -- recommended over inline)

**Why `api/budget.py` over inline in `sherlock_wrapper.py`:**
- `health.py` reads counters; `sherlock_wrapper.py` writes them. Inlining creates an `api/ -> modules/` import dependency that conflicts with Phase 15 D-01 leaf rules.
- Testable in isolation without httpx mocks.
- Consistent with `api/config.py` leaf pattern: `budget.py` imports only from `api/config.py`.

```python
# api/budget.py -- module-level state (in-process, resets on container restart per D-16)
from __future__ import annotations
from datetime import datetime, timezone, date
from loguru import logger
from api.config import THORDATA_DAILY_BUDGET_BYTES

_bytes_today: int = 0
_requests_today: int = 0
_current_day: date = datetime.now(timezone.utc).date()
_proxy_active: bool = False  # set True in lifespan after health check passes

def _maybe_reset() -> None:
    """Lazy UTC day rollover check. Called at the start of every budget operation."""
    global _bytes_today, _requests_today, _current_day
    today = datetime.now(timezone.utc).date()
    if today != _current_day:
        logger.info(
            "Thordata budget reset: new UTC day. prev_bytes={} prev_reqs={}",
            _bytes_today, _requests_today
        )
        _bytes_today = 0
        _requests_today = 0
        _current_day = today

def record_usage(bytes_used: int) -> None:
    global _bytes_today, _requests_today
    _maybe_reset()
    _bytes_today += bytes_used
    _requests_today += 1
    soft_bytes = THORDATA_DAILY_BUDGET_BYTES // 2  # 500MB soft threshold
    if _bytes_today > soft_bytes:
        logger.warning(
            "Thordata SOFT budget exceeded: {:.1f}MB used",
            _bytes_today / 1_048_576
        )

def is_hard_limit_exceeded() -> bool:
    _maybe_reset()
    return _bytes_today >= THORDATA_DAILY_BUDGET_BYTES

def get_metrics() -> dict:
    _maybe_reset()
    budget_mb = THORDATA_DAILY_BUDGET_BYTES / 1_048_576
    used_mb = _bytes_today / 1_048_576
    return {
        "bytes_today_mb": round(used_mb, 2),
        "requests_today": _requests_today,
        "budget_remaining_pct": round(max(0.0, (1.0 - used_mb / budget_mb) * 100), 1),
        "proxy_active": _proxy_active,
    }
```

**UTC reset strategy -- lazy check (recommended):** No background `asyncio.create_task` needed. `_maybe_reset()` fires on the first budget operation after UTC midnight. Lower memory footprint; no extra tracked task in the orchestrator registry.

### Pattern 6: Proxy 1x Retry with IP Rotation

```python
# Per D-06: retry exactly once, force new IP by using different sessid
async def _check_platform_with_retry(
    primary_client: httpx.AsyncClient,
    rotate_client: httpx.AsyncClient,
    username: str,
    platform: dict,
    per_search_counter: dict,
) -> PlatformResult:
    """
    Try platform with primary sticky-session proxy.
    On ProxyError: retry once with rotate_client (different sessid = forced IP rotation).
    On second ProxyError: mark error='proxy_unavailable' (D-06).
    """
    try:
        return await _check_platform(primary_client, username, platform, per_search_counter)
    except httpx.ProxyError:
        logger.warning(
            "Proxy error on platform={}, retrying with IP rotation",
            platform["name"]
        )
        try:
            return await _check_platform(rotate_client, username, platform, per_search_counter)
        except httpx.ProxyError:
            return PlatformResult(
                platform=platform["name"],
                url=platform["url"].format(username=username),
                category=platform.get("category", ""),
                icon=platform.get("icon", ""),
                error="proxy_unavailable",
                state="not_found",
                confidence=0,
            )
```

### Pattern 7: Updated Dataclasses

```python
@dataclass
class PlatformResult:
    platform: str = ""
    url: str = ""
    found: bool = False        # backward compat -- True if state != 'not_found'
    category: str = ""
    icon: str = ""
    confidence: int = 0        # NEW: 0-100 score
    state: str = "not_found"   # NEW: 'confirmed' | 'likely' | 'not_found'
    error: Optional[str] = None

@dataclass
class SherlockResult:
    username: str = ""
    success: bool = False
    found: list[PlatformResult] = field(default_factory=list)      # confirmed state only
    likely: list[PlatformResult] = field(default_factory=list)     # NEW: likely state
    not_found: list[PlatformResult] = field(default_factory=list)
    errors: list[PlatformResult] = field(default_factory=list)
    error: str = ""
    source: str = "internal"
    proxy_used: bool = False   # NEW: for D-H13 audit log
```

### Pattern 8: Username Validator -- Route Layer (NOT schemas.py)

**Key finding:** Pydantic v2 `@field_validator` raises `ValueError`, which FastAPI converts to HTTP **422** (not 400). D-H9 requires HTTP 400 with no echo of input. Phase 15 D-01 also forbids importing `HTTPException` in `schemas.py` (leaf module).

**Solution:** Validate in the route or service layer and raise `HTTPException(400)` explicitly:

```python
# In api/routes/search.py or api/services/search_service.py (before calling search_username)
import re
import hashlib

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_REJECT_CHARS = re.compile(r"[/:?#&=\s\x00]")

def _validate_sherlock_username(username: str) -> None:
    """
    Raise HTTPException(400) if username is invalid (D-H8/D-H9).
    No echo of input -- generic message only.
    """
    if not username or _REJECT_CHARS.search(username) or not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="Invalid username format")

def _hash_username_for_log(username: str) -> str:
    """SHA256 truncated 8 chars for audit logs (D-H13). Never log plaintext."""
    return hashlib.sha256(username.encode()).hexdigest()[:8]
```

### Pattern 9: Budget Circuit Breaker in Search Route

```python
# In api/routes/search.py or api/services/search_service.py -- BEFORE calling search_username
import api.budget as _budget

# Before Sherlock invocation:
if _budget.is_hard_limit_exceeded():
    raise HTTPException(
        status_code=503,
        detail="Daily proxy bandwidth limit reached",
        headers={"Retry-After": "86400"},
    )
```

### Anti-Patterns to Avoid

- **`proxies=` (plural):** Deprecated in 0.27.x, removed in 0.28.0. Use `proxy=` singular.
- **`resp.text[:cap]` for body capping:** Does NOT limit downloaded bytes. Use `client.stream()` + `aiter_bytes()`.
- **`asyncio.TimeoutError` in `_check_platform`:** httpx raises `httpx.TimeoutException` (separate class). Existing catch is dead code. Fix: replace with `except httpx.TimeoutException:`.
- **`sesstime-60` literally:** Thordata sesstime is in MINUTES. 60 = 60 minutes. Use `sesstime-2`.
- **Background asyncio task for daily budget reset:** Lazy `_maybe_reset()` is simpler and adds no memory cost.
- **Pydantic validator for HTTP 400:** Pydantic raises ValueError -> FastAPI wraps as 422. Validate in route layer instead.
- **Bare `except Exception` in `_check_platform`:** CLAUDE.md prohibition. Catch named httpx types only; re-raise `ProxyError` for retry.
- **Inlining budget state in `sherlock_wrapper.py`:** Creates fragile cross-layer import from `api/routes/health.py` to `modules/`. Use `api/budget.py`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sticky session construction | Custom proxy session management service | `urllib.parse.urlparse` + string interpolation in username | Thordata uses username field encoding; no separate API call needed |
| Credential masking | Custom log filter class | `urlparse(url).hostname + ":" + str(port)` | 2-line extraction, zero dependencies |
| Per-domain rate limiting | Custom sliding window | `OutboundRateLimiter` token bucket already specified in CLAUDE.md | Designed exactly for this use case |
| Body byte cap | Custom streaming middleware | `client.stream("GET", url)` + `aiter_bytes()` | httpx built-in; enforces real cap |
| UTC day reset | Scheduled background task | Lazy `_maybe_reset()` on every counter access | No task overhead, no memory leak |
| search_id generation | UUID4 or timestamp | `secrets.token_hex(8)` (16-char hex, alphanumeric-safe) | Cryptographically safe, alphanumeric, correct sessid format |

---

## Negative Markers Per Platform

Research from sherlock-project/sherlock upstream data.json (fetched via raw.githubusercontent.com 2026-04-29) and platform behavior analysis. These strings appear on not-found pages and reliably reject false positives when a positive claim would otherwise score >= LIKELY_THRESHOLD.

**Confidence level:** MEDIUM -- strings verified from upstream Sherlock community maintenance; should be validated by manual test against each platform with a known-missing username before final plan.

| Platform | Current claim_type | Recommended negative_markers |
|----------|--------------------|-------------------------------|
| GitHub | status_code | `["Not Found", "Page not found"]` |
| GitLab | status_code | `["not found", "404 Page Not Found"]` |
| Twitter/X | text_absent | `["this account doesn't exist"]` (already claim_value; add for belt-and-suspenders) |
| Instagram | text_absent | `["sorry, this page isn't available", "page not found"]` |
| TikTok | text_absent | `["couldn't find this account", "\"statusCode\":10221"]` |
| Reddit | text_absent | `["sorry, nobody on reddit goes by that name"]` |
| LinkedIn | text_absent | `["page not found", "this page doesn't exist"]` |
| Pinterest | text_absent | `["sorry! we couldn't find that page"]` |
| YouTube | text_absent | `["this page isn't available", "404 not found"]` |
| Twitch | text_absent | `["sorry. unless you've got a time machine"]` |
| Steam | text_absent | `["the specified profile could not be found"]` |
| Keybase | status_code | `["not found", "user not found"]` |
| HackerNews | text_present | `["no such user", "sorry"]` |
| Dev.to | status_code | `["page not found", "404 not found"]` |
| Medium | text_absent | `["page not found"]` |
| Mastodon | status_code | `["not found", "this resource was not found"]` |
| Flickr | text_absent | `["page not found"]` |
| Vimeo | text_absent | `["sorry, we couldn't find that page"]` |
| SoundCloud | text_absent | `["we can't find that user"]` |
| Spotify | text_absent | `["page not found", "user not found"]` |
| DockerHub | status_code | `["not found", "page not found"]` |
| NPM | text_absent | `["we're sorry, you've reached a 404"]` |
| PyPI | status_code | `["not found", "404: page not found"]` |
| Telegram | text_present | `["if you have telegram, you can contact"]` -- absence of `tgme_page_title` already caught by claim |
| Snapchat | text_absent | `["sorry, we couldn't find"]` |

**Implementation notes:**
- All comparisons are case-insensitive (`marker.lower() in body_lower`).
- For platforms where claim_type is `text_absent` and the negative_marker IS the claim_value, the negative_marker is redundant but harmless (adds belt-and-suspenders against score-gaming).
- Negative markers should be SHORT, distinctive substrings -- not full sentences, which are fragile to minor platform copy changes.

---

## Runtime State Inventory

Phase 16 is a code-only change. No rename, no rebrand, no migration.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None -- Thordata budget counter is in-memory only; no DB records involved | None |
| Live service config | None -- `THORDATA_PROXY_URL` is a NEW env var; no existing config changes | Add to `.env` (real value, user supplies), `.env.example` (placeholder, D-H7) |
| OS-registered state | None -- no task scheduler, systemd, or pm2 entries affected | None |
| Secrets/env vars | `THORDATA_PROXY_URL` is NEW (not currently in `.env`). User confirmed value exists. | Add to `.env` manually; add placeholder to `.env.example` |
| Build artifacts | None -- no compiled binaries, pip egg-info, or Docker image tags affected by code changes | None |

---

## Common Pitfalls

### Pitfall 1: asyncio.TimeoutError vs httpx.TimeoutException (EXISTING BUG IN sherlock_wrapper.py)

**What goes wrong:** Current `_check_platform` at line 306 catches `asyncio.TimeoutError`. httpx raises `httpx.TimeoutException` -- a completely different class, not a subclass of `asyncio.TimeoutError`. The existing catch is dead code. Timeout errors currently fall through to `except httpx.HTTPError` at best.

**Confirmed:** `httpx.TimeoutException.__bases__ == (httpx.TransportError,)`. `asyncio.TimeoutError` is not in httpx's MRO anywhere. `issubclass(asyncio.TimeoutError, httpx.TimeoutException) == False`.

**How to avoid:** Replace `except asyncio.TimeoutError:` with `except httpx.TimeoutException:` in `_check_platform`. This is a required fix for Phase 16, not optional cleanup.

### Pitfall 2: sesstime Unit Mismatch (D-03 Intent vs Thordata Reality)

**What goes wrong:** D-03 specifies `-sesstime-60` intending 60 seconds. Thordata documents sesstime in MINUTES. `sesstime-60` = 60 minutes of IP lock per search -- rapidly depletes the Thordata sticky pool.

**How to avoid:** Use `sesstime-2` (2 minutes = 120 seconds). Covers the full ~30s search plus 1x retry margin. The planner must document this unit correction explicitly so the implementer does not blindly copy D-03's literal string.

### Pitfall 3: httpx.ProxyError Catch Order (Must Come Before httpx.HTTPError)

**Confirmed exception hierarchy:** `ProxyError -> TransportError -> RequestError -> HTTPError -> Exception`. Catching `httpx.HTTPError` before `httpx.ProxyError` in `_check_platform` would swallow proxy errors that should trigger the retry path. `httpx.ProxyError` MUST be caught first (and re-raised to the caller for retry logic) before the `httpx.HTTPError` fallback.

**Correct order in `_check_platform`:**
1. `httpx.ProxyError` -- re-raise (trigger retry)
2. `httpx.TimeoutException` -- set error="timeout"
3. `httpx.ConnectError` -- set error="connection_error"
4. `httpx.HTTPStatusError` -- set error="http_NNN"
5. `httpx.HTTPError` -- set error=str(exc)[:80]

### Pitfall 4: resp.text[:cap] Body Cap is Cosmetic (EXISTING BUG)

**What goes wrong:** `resp.text` triggers a full body read via httpx before the slice. The 512KB slice cap in the existing code does not limit downloaded bytes -- it only limits how much of the already-downloaded text is processed. On 2-5MB platform pages, peak memory per concurrent Sherlock search can reach 125MB above baseline.

**How to avoid:** Use `client.stream("GET", url)` + `aiter_bytes(chunk_size=8192)` with early break at `cap_bytes` (see Pattern 4). This is a required fix for Phase 16.

**Memory calculation:** Without fix: 25 concurrent x 5MB = 125MB peak. With real 256KB cap: 25 x 256KB = ~6MB peak. Difference is critical on the 1GB VPS with < 200MB resting requirement.

### Pitfall 5: Cloudflare Challenge False Positives

**What goes wrong:** LinkedIn, Instagram, TikTok return Cloudflare challenge pages to DO IPs. Status 403 with `cf-mitigated: challenge` header. Current claim logic (text_absent of not-found string) interprets a challenge page as found=True, producing false positives that the proxy was supposed to prevent during a degraded proxy state.

**Detection:** Cloudflare officially documents `cf-mitigated: challenge` header as the stable, reliable indicator. Using `client.stream()` (Pattern 4) makes response headers available before body consumption.

**How to avoid:** In `_check_platform`, after `_fetch_with_cap` returns headers, check `headers.get("cf-mitigated") == "challenge"` BEFORE calling `_compute_confidence`. If detected: `error = "cf_challenge"`, confidence = 0, state = "not_found".

### Pitfall 6: search_service.py Serializer Must Include `likely` and New Fields

**What goes wrong:** The current SSE event at `search_service.py` lines 364-372 iterates only `sherl.found` and emits `{platform, url, category, icon}`. The new `sherl.likely` list and `confidence`/`state` fields are not serialized.

**How to avoid:** Update the `yield event({"type": "sherlock", ...})` block to include:
- `"found"`: confirmed platforms with `{platform, url, category, icon, state: "confirmed", confidence: int}`
- `"likely"`: likely platforms with `{platform, url, category, icon, state: "likely", confidence: int}`
- `"found_count"`: `len(sherl.found)` (confirmed only, backward compat)
- `"likely_count"`: `len(sherl.likely)` (new)

Per D-H2: do NOT include raw signal scores (status_pts, text_pts, size_pts) in the response.

### Pitfall 7: Per-Search Byte Cap Under asyncio.gather

**What goes wrong:** D-17's 1MB per-search cap is cumulative across all 25 concurrent platform calls. `asyncio.gather` fires all simultaneously -- there is no natural sequencing to enforce a running total mid-flight.

**How to avoid:** Pass a shared `{"bytes": 0}` dict by reference to each `_check_platform` call. Each call adds its bytes after `_fetch_with_cap` returns. After `asyncio.gather` completes, check if total exceeded 1MB and log partial result. Do NOT attempt to cancel in-flight tasks mid-gather to enforce the cap (complex, error-prone). The 1MB cap is a soft ceiling -- accepted overshoot is bounded by (25 platforms x 256KB cap) = ~6MB worst case, not unbounded.

### Pitfall 8: Import Cycle Risk if Budget Tracker Inlined in sherlock_wrapper.py

**What goes wrong:** `api/routes/health.py` needs to read budget counters. If counters live in `modules/sherlock_wrapper.py`, health.py imports from modules/, creating a `api/ -> modules/` dependency. While not a cycle per se, it violates the intent of Phase 15 D-01 (api/ should not depend on modules/ for non-functional state).

**How to avoid:** Put budget state in `api/budget.py`. It imports only from `api/config.py`. Both `sherlock_wrapper.py` and `health.py` import from `api/budget.py`. No cycle, clean dependency graph.

---

## Environment Availability Audit

Phase 16 is a code-change phase with no new external tools or CLIs required.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| httpx | Proxy routing, async HTTP | Yes | 0.27.2 (in requirements.txt) | N/A |
| pydantic | Username validator | Yes | 2.8.2 (in requirements.txt) | N/A |
| respx | Test mocking | Yes | 0.22.0 (dev install) | N/A |
| Thordata proxy service | Outbound routing for Sherlock | Assumed (user confirmed URL in .env) | residential | D-07: non-blocking startup check; degrade to no-proxy + WARNING if unreachable |
| `api.ipify.org` | Startup health check (D-07) | Not locally probed (external) | -- | If unreachable: degrade to no-proxy mode + WARNING; app does NOT crash |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- Thordata proxy: If unreachable at startup, D-07 specifies non-blocking degradation to direct mode with WARNING log. Direct mode may produce false negatives on DO-blocked platforms (LinkedIn, Instagram, TikTok) but does not crash the app.

---

## Code Examples

### Config Additions (api/config.py)

```python
# Thordata proxy -- None means proxy disabled (Sherlock uses direct DO IP)
THORDATA_PROXY_URL: str | None = os.getenv("THORDATA_PROXY_URL")

# Budget thresholds stored as bytes (D-18)
_THORDATA_DAILY_BUDGET_MB: int = int(os.getenv("THORDATA_DAILY_BUDGET_MB", "1024"))
THORDATA_DAILY_BUDGET_BYTES: int = _THORDATA_DAILY_BUDGET_MB * 1_048_576

_THORDATA_PER_SEARCH_CAP_MB: int = int(os.getenv("THORDATA_PER_SEARCH_CAP_MB", "1"))
THORDATA_PER_SEARCH_CAP_BYTES: int = _THORDATA_PER_SEARCH_CAP_MB * 1_048_576

# Confidence thresholds -- tunable without redeploy (D-11)
SHERLOCK_CONFIRMED_THRESHOLD: int = int(os.getenv("SHERLOCK_CONFIRMED_THRESHOLD", "70"))
SHERLOCK_LIKELY_THRESHOLD: int = int(os.getenv("SHERLOCK_LIKELY_THRESHOLD", "40"))
```

### .env.example Content (to be created, D-H7)

```
# Thordata residential rotating proxy
# Format: http://td-customer-YOUR_USER:YOUR_PASS@t.pr.thordata.net:9999
# Leave unset to disable proxy (Sherlock will use direct DO IP -- may be blocked by LinkedIn/Instagram/TikTok)
THORDATA_PROXY_URL=http://td-customer-YOUR_USER:YOUR_PASS@t.pr.thordata.net:9999

# Thordata bandwidth budget limits
THORDATA_DAILY_BUDGET_MB=1024
THORDATA_PER_SEARCH_CAP_MB=1

# Sherlock confidence scoring thresholds (0-100)
SHERLOCK_CONFIRMED_THRESHOLD=70
SHERLOCK_LIKELY_THRESHOLD=40
```

### /health/thordata Endpoint Pattern

```python
# api/routes/health.py -- add after existing /health/memory
# Source: matches existing /health/memory pattern exactly (admin-gated, RL_ADMIN_LIMIT)
from api import budget as _budget

@router.get("/health/thordata")
@limiter.limit(RL_ADMIN_LIMIT)
async def health_thordata(
    request: Request,
    _: dict = Depends(get_admin_user),  # D-H14: admin-gated
):
    """Thordata proxy usage metrics -- admin only. Resets on container restart."""
    return _budget.get_metrics()
```

### Startup Health Check Addition (api/main.py lifespan)

```python
# Add inside lifespan(), after existing startup steps, before yield
from api.config import THORDATA_PROXY_URL
import api.budget as _budget
from modules.sherlock_wrapper import _masked_proxy_log  # or define in api/budget.py

if THORDATA_PROXY_URL:
    try:
        async with httpx.AsyncClient(
            proxy=THORDATA_PROXY_URL,
            timeout=httpx.Timeout(10.0, connect=5.0),
        ) as hc:
            await hc.head("https://api.ipify.org")
            logger.info(
                "Thordata proxy OK (proxy={})",
                _masked_proxy_log(THORDATA_PROXY_URL)
            )
            _budget._proxy_active = True
    except Exception:  # noqa: BLE001
        # JUSTIFIED: D-07 explicitly specifies non-blocking degradation.
        # This is startup lifespan, not an endpoint -- CLAUDE.md per-layer rule
        # permits broad catch here because failure IS the intended degradation path.
        logger.warning(
            "Thordata proxy health check FAILED (proxy={}) -- degrading to no-proxy mode",
            _masked_proxy_log(THORDATA_PROXY_URL) if THORDATA_PROXY_URL else "unset"
        )
        _budget._proxy_active = False
```

### Per-Search Audit Log (D-H13)

```python
# At the end of search_username(), before returning SherlockResult
import hashlib

username_hash = hashlib.sha256(username.encode()).hexdigest()[:8]
logger.info(
    "Sherlock search complete | username_hash={} bytes_consumed={} proxy_used={} "
    "confirmed={} likely={} errors={}",
    username_hash,
    per_search_counter["bytes"],
    bool(THORDATA_PROXY_URL and _budget._proxy_active),
    len(result.found),
    len(result.likely),
    len(result.errors),
)
```

---

## State of the Art

| Old Approach | Current Approach | Introduced | Phase 16 Impact |
|--------------|------------------|-----------|-----------------|
| `httpx.proxies=` dict | `httpx.proxy=` singular URL string | httpx 0.26.0 deprecated; 0.28.0 removed | Must use `proxy=` -- project is on 0.27.2 |
| `resp.text[:cap]` fake body cap | `client.stream()` + `aiter_bytes()` | httpx 0.x (streaming always existed) | Fix required in Phase 16 as part of 256KB real cap |
| `asyncio.TimeoutError` catch | `httpx.TimeoutException` catch | httpx always raised its own -- existing catch is wrong | Fix required in Phase 16 |
| Binary found/not-found | 3-state confirmed/likely/not_found | Phase 16 introduces | New `state` + `confidence` fields on PlatformResult |
| `pydantic.validator` (v1) | `@field_validator` + `@classmethod` (v2) | Pydantic 2.0 | Already using v2 in existing SearchRequest |
| Cloudflare status 503 JS challenge | Status 403 (changed March 2023) | Cloudflare 2023-03-01 | Use `cf-mitigated` header, not status code |

---

## Open Questions

1. **Cloudflare challenge detection via streaming headers**
   - What we know: `cf-mitigated: challenge` header is Cloudflare's officially documented stable detection method. Using `client.stream()` makes `resp.headers` available before body consumption.
   - What's unclear: Whether the streaming approach's `resp.headers` dict in httpx 0.27.2 is populated before `aiter_bytes()` is called.
   - Recommendation: In `_fetch_with_cap`, capture `dict(resp.headers)` immediately after entering the `async with client.stream(...)` block, before iterating bytes. Return headers alongside body bytes. This is safe -- httpx populates headers from the HTTP response head, which arrives before the body.

2. **sesstime=2 vs D-03's sesstime=60 -- planner must document the correction**
   - What we know: D-03 is locked but contains a unit error (intends seconds, Thordata uses minutes). The planner cannot silently "fix" a locked decision -- it must document the correction.
   - Recommendation: Plan should state: "D-03 specifies `sesstime-60`. Research confirms Thordata sesstime is in MINUTES. Implementing as `sesstime-2` (2 minutes = 120 seconds) to match D-03's stated intent of covering 'full Sherlock search plus retry margin.'"

3. **Per-search byte cap enforcement under asyncio.gather**
   - What we know: Shared `{"bytes": 0}` dict passed by reference works at the Python level (GIL protects simple integer ops on CPython). But the cap is checked post-gather, not mid-flight.
   - What's unclear: Whether the planner wants wave-based execution (check cap between waves) or post-gather filtering.
   - Recommendation: Post-gather filtering is simpler and lower latency. The worst-case overshoot is bounded: 25 platforms x 256KB = 6MB, well under the 1MB soft cap intent. Document as acceptable overshoot.

4. **Frontend render.js: how to display `likely` cards**
   - What we know: Current `render.js` lines 489-517 iterate only `s.found`. The new `s.likely` list needs rendering with an "Unverified" badge and muted styling.
   - What's unclear: Whether `likely` cards go in the same `.social-cards-grid` as `confirmed` cards, or a separate section.
   - Recommendation: Same grid, different CSS class (`social-card--unverified` with opacity or muted amber). Update `badge.textContent = s.found_count` to `s.found_count + s.likely_count` (or show "N (M unverified)" if design allows).

5. **OutboundRateLimiter instantiation scope**
   - What we know: CLAUDE.md specifies `OutboundRateLimiter(calls_per_second=2.0)` as a global instance. D-04 requires 1 req/s per domain.
   - What's unclear: Should one `OutboundRateLimiter` instance be shared across all `search_username()` calls (module-level), or created fresh per call?
   - Recommendation: Module-level singleton in `sherlock_wrapper.py`. This correctly enforces domain-level rate limiting across concurrent searches (prevents two simultaneous searches from both hammering the same platform at 1 req/s each).

---

## Project Constraints (from CLAUDE.md)

| Constraint | Phase 16 Application |
|------------|---------------------|
| `except Exception` generic PROHIBITED in agents | `_check_platform` catches named httpx exceptions only; re-raises `ProxyError` for retry |
| All validation at backend, never frontend | Username validator in route layer (raises 400); `state` field computed backend-only |
| `httpx.AsyncClient` with explicit timeout -- never `requests` sync | Already compliant; `proxy=` added to existing client construction |
| Outbound rate limiting: `OutboundRateLimiter` token bucket, 1 req/s per domain | Module-level singleton `OutboundRateLimiter(calls_per_second=1.0)` in `sherlock_wrapper.py` |
| Memory < 200MB resting; no unbounded collections | `aiter_bytes()` enforces 256KB real cap; budget counter is O(1) state (4 primitives) |
| Loguru, never PII, never plaintext target | `hashlib.sha256(username.encode()).hexdigest()[:8]` before every log statement |
| `api/config.py` is ONLY place for env var loading | All 6 new env vars added to `api/config.py` only |
| `api/schemas.py` is LEAF module (Phase 15 D-01) | Username validator goes in route layer, NOT schemas.py |
| Proxy URL never logged -- `host:port` only | `_masked_proxy_log()` helper used in all log statements that reference proxy |
| Docker image < 250MB | Zero new pip packages -- no image size impact |

---

## Sources

### Primary (HIGH confidence)
- Thordata official docs `doc.thordata.com/doc/proxies/residential-proxies/making-request` -- sticky session format, sesstime unit (MINUTES), sessid constraints, host/port confirmed
- Thordata official blog `thordata.com/blog/quick-start-guides/residential-proxies-quick-start-guide` -- full URL format, Python integration
- httpx 0.27.2 runtime introspection -- `AsyncClient.__init__` parameters: both `proxy` (singular) and `proxies` (plural) present; `proxy=` is the non-deprecated form
- httpx exception hierarchy -- confirmed via `httpx.ProxyError.__mro__`, `httpx.TimeoutException.__mro__` runtime inspection on installed package
- Cloudflare official docs `developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/` -- `cf-mitigated: challenge` header
- Installed package versions: httpx==0.27.2, pydantic==2.8.2, respx==0.22.0, pytest-asyncio==1.3.0 (confirmed via pip show)

### Secondary (MEDIUM confidence)
- sherlock-project/sherlock upstream data.json (raw.githubusercontent.com, fetched 2026-04-29) -- error type and message patterns per platform
- httpx official docs `python-httpx.org/advanced/proxies/` -- `proxy=` parameter syntax, `mounts=` approach
- httpx GitHub discussions #3490 / #3425 -- confirms `proxies=` removed in 0.28.0; `proxy=` is current form

### Tertiary (LOW confidence -- flag for validation)
- Platform-specific negative_markers strings: derived from upstream Sherlock data.json + analysis. Should be validated by manual test (curl with known-missing username against each platform) before finalizing PLATFORMS dict.
- Cloudflare body-text markers (fallback if headers unavailable): LOW confidence -- challenge page HTML changes frequently. Prefer `cf-mitigated` header detection.

---

## Metadata

**Confidence breakdown:**
- Thordata sticky session syntax: HIGH -- fetched from official docs, cross-verified with blog
- httpx proxy API (`proxy=` vs `proxies=`): HIGH -- confirmed via runtime introspection
- httpx exception hierarchy: HIGH -- confirmed via `__mro__` inspection on installed 0.27.2
- Confidence scoring logic: HIGH -- pure math per locked decisions D-08/D-09/D-10
- Budget tracker design: HIGH -- standard Python module-level state pattern
- Negative markers strings: MEDIUM -- from upstream Sherlock community data; needs manual validation
- Cloudflare detection (header-based): MEDIUM -- officially documented stable contract
- Cloudflare detection (body-text fallback): LOW -- changes frequently

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days) for httpx/pydantic/Thordata API; 7 days for Cloudflare challenge markers
