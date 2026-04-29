# Phase 16: Sherlock False-Positive Filter + Thordata Proxy Integration - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Reduce Sherlock detection false-positives via multi-signal confidence scoring AND route Sherlock outbound traffic through Thordata residential rotating proxy to bypass DigitalOcean IP blocks (LinkedIn / Instagram / TikTok / etc).

**In scope:**
- `modules/sherlock_wrapper.py` — proxy integration + FP filter logic
- `api/config.py` — Thordata config + budget constants
- `PLATFORMS` dict — enrich with `negative_markers` per site
- `/health` admin metrics — Thordata bytes/requests today
- Daily budget tracker (in-memory, UTC reset)
- Per-search byte cap
- Pydantic username validator hardening

**Out of scope (deferred):**
- Migrate to upstream Sherlock `data.json` (300+ platforms) — would inflate UI + bandwidth, regresses D-06 (4 fields ceiling)
- Proxy for OathNet / SpiderFoot / Holehe — paid API + internal container, no DO block issue
- Sherlock CLI fallback restructure — current `prefer_cli=False` default unchanged
- New OSINT modules / new platforms

</domain>

<decisions>
## Implementation Decisions

### Proxy Scope (Area 1 — locked by Claude, no discussion)
- **D-01:** Proxy applied ONLY to `modules/sherlock_wrapper.py`. OathNet (paid API) and SpiderFoot (internal container) bypass proxy entirely.

### Proxy Session Strategy (Area 2)
- **D-02:** Hybrid session: sticky session per `search_id` (same residential IP for all 25 platforms in one search), rotate IP only on retry after 4xx / 429 / timeout / proxy error.
- **D-03:** Sticky session TTL = **60 seconds** via Thordata username suffix (`-sessid-<search_id>-sesstime-60`). Covers full Sherlock search (~10-30s) plus retry margin.
- **D-04:** Per-domain outbound rate limit = **1 req/s per domain** (CLAUDE.md outbound rate limiter requirement).
- **D-05:** `httpx.AsyncClient` `max_connections=8` when proxy active (down from 15). Reduces Thordata bandwidth, throughput still adequate (25 platforms / ~3 waves).

### Proxy Fallback (Area 3)
- **D-06:** On proxy failure (timeout / 502 / auth / `httpx.ProxyError`): retry exactly **1×** through proxy (forces IP rotation). On second failure, mark platform as `error: proxy_unavailable`. **No direct (proxy-bypass) fallback** — DigitalOcean IP would re-trigger blocks and produce false `not_found`.
- **D-07:** Startup health check via `HEAD https://api.ipify.org` through proxy in FastAPI `lifespan`. Logs returned IP. **Non-blocking** — failure degrades to no-proxy mode + WARNING log; app does not crash.

### False-Positive Filter (Area 4)
- **D-08:** Multi-signal confidence score (0-100) per platform check:
  ```
  status_code match    → +40
  text marker match    → +40
  size sanity (>3KB)   → +20
  total cap            → 100
  ```
- **D-09:** Per-platform `negative_markers` list — strings that REJECT a match even if positive claim_value hits. Example: GitHub status=200 + body contains `"Page not found"` → confidence dropped to 0. Handles custom 404s rendered with HTTP 200.
- **D-10:** Display thresholds (backend-decided, see D-H1):
  - score >= 70 → state `confirmed`
  - score 40-69 → state `likely`
  - score < 40  → state `not_found`
- **D-11:** Thresholds tunable via env vars `SHERLOCK_CONFIRMED_THRESHOLD` (default 70) and `SHERLOCK_LIKELY_THRESHOLD` (default 40). No deploy needed for rebalance.
- **D-12:** Existing 3 claim_types (`status_code`, `text_present`, `text_absent`) preserved as scoring inputs — no breaking change to PLATFORMS dict structure beyond adding `negative_markers`.

### Result Confidence Display (Area 5)
- **D-13:** 3-state output instead of binary found/not-found:
  - `confirmed` — full card render, amber accent
  - `likely` — card render with `Unverified` badge + muted color
  - `not_found` — not rendered
- **D-14:** API response includes `state: "confirmed" | "likely" | "not_found"` and `confidence: int`. Frontend MUST consume `state` directly — never recompute from `confidence`.

### Cost / Budget Controls (Area 6)
- **D-15:** Body cap retained at 512KB globally (F4 guarantee, no regression). Sherlock-specific cap added: **256KB** per response (profile pages well under, landing-page spam pages cut off).
- **D-16:** Daily budget tracker — in-memory counter `_thordata_bytes_today` + `_thordata_requests_today`, reset at 00:00 UTC.
  - SOFT threshold = 500MB → log WARNING.
  - HARD threshold = 1GB → circuit breaker: Sherlock-touching endpoints return HTTP 503 + `Retry-After: 86400`. App restarts reset counter (acceptable trade-off vs persistent state).
- **D-17:** Per-search byte cap = **1MB total** (25 platforms × ~40KB average). Exceeded → abort remaining platforms, return partial result + log INFO.
- **D-18:** Budget values configurable via env: `THORDATA_DAILY_BUDGET_MB` (default 1024), `THORDATA_PER_SEARCH_CAP_MB` (default 1).
- **D-19:** New `/health` (admin-gated) fields: `thordata.bytes_today_mb`, `thordata.requests_today`, `thordata.budget_remaining_pct`, `thordata.proxy_active: bool`.

### Security Hardening — "Never Trust Frontend" (CLAUDE.md core rule)
- **D-H1:** Confidence thresholds (70 / 40) applied EXCLUSIVELY backend. API delivers pre-classified `state` field. Frontend never recomputes state from `confidence` (read-only).
- **D-H2:** Per-signal raw scores (status_pts / text_pts / size_pts) NOT exposed to frontend. Only final `confidence: int` + `state` returned. Smaller payload + reduced manipulation surface.
- **D-H3:** `negative_markers` live in backend `PLATFORMS` dict only. Never serialized in API response.
- **D-H4:** Daily budget enforcement, per-search cap, and per-domain rate limit decided backend. No header / query param can bypass them.
- **D-H5:** `THORDATA_PROXY_URL` read only via `api/config.py` `os.getenv`. Never log full URL — mask `user:pass` in any log statement, log only `host:port`.
- **D-H6:** Proxy errors surfaced to client as generic `"upstream_unavailable"`. Full exception (with proxy URL) goes to internal log only via `logger.exception()`.
- **D-H7:** `.env` already in `.gitignore`. Add `THORDATA_PROXY_URL=http://USER:PASS@HOST:PORT` placeholder to `.env.example` (create file if absent) so deploy docs exist without credential leak.
- **D-H8:** Pydantic validator on `username` input: regex `^[A-Za-z0-9_.-]{1,64}$`. Applied at endpoint boundary BEFORE invoking `sherlock_wrapper.search_username()`.
- **D-H9:** Reject usernames containing `/`, `:`, `?`, `#`, `&`, `=`, whitespace, null byte. Return HTTP 400 with generic message (no echo of input).
- **D-H10:** Audit each `claim_value` in `PLATFORMS` dict — confirm none accept user input dynamically. Static literals only.
- **D-H11:** `RL_SEARCH_LIMIT=10/minute` per user retained. Internal Sherlock concurrency stays bounded by global `Semaphore(5)`.
- **D-H12:** Daily-budget circuit breaker returns explicit 503 + `Retry-After`. Never silently drop request.
- **D-H13:** Per-search log line (loguru, INFO): `username_hash` (SHA256 truncated 8 chars), `bytes_consumed`, `proxy_used: bool`, `confirmed_count`, `likely_count`, `errors_count`. Username plaintext NEVER logged.
- **D-H14:** `/health` Thordata metrics admin-gated via `Depends(get_admin_user)` — bandwidth-usage patterns are sensitive. Pattern matches existing `/health/memory`.
- **D-H15:** Exception handling (CLAUDE.md per-layer pattern):
  - In `_check_platform`: catch only `httpx.ProxyError` (NEW), `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.HTTPStatusError`, `httpx.HTTPError`. NO bare `except Exception`.
  - Errors propagate to TaskGroup for cancellation semantics.
  - Endpoint layer converts unexpected exceptions to `HTTPException(500, "Internal error")` after `logger.exception()`.

### Claude's Discretion
- Internal naming of helper functions / private constants in `sherlock_wrapper.py`.
- Whether to extract budget tracker into separate `api/budget.py` module or inline in `sherlock_wrapper.py` (depends on testability).
- Exact format of `/health` Thordata payload structure (nested object vs flat keys) — keep consistent with existing `/health` style.
- Specific `negative_markers` strings per platform — researcher should pick observed real-world 404 page text per site.
- Whether to use Thordata sticky session via username syntax (`-sessid-X-sesstime-N`) or via separate session endpoint — researcher to confirm with Thordata docs.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Constraints
- `CLAUDE.md` — Filosofia central (regras 1-5), padrão exception handling per-layer, rate limiting outbound (`OutboundRateLimiter` token bucket), Pydantic input validation rule, "Não Confie no Frontend" mandate.
- `.planning/PROJECT.md` — Milestone scope, brand Amber/Noir non-negotiable.
- `.planning/STATE.md` (entry 2026-04-29) — Phase 16 registration + roadmap evolution context.

### Existing Code (must read before modifying)
- `modules/sherlock_wrapper.py` — Current implementation: 25 PLATFORMS dict, async engine `_check_platform`, claim_types (`status_code` / `text_present` / `text_absent`), `verify=False` SSL config, body cap 512KB existing.
- `api/config.py` — Where `THORDATA_PROXY_URL`, budget constants, threshold env vars MUST be added (leaf module rule from Phase 15 D-01).
- `api/routes/search.py` — Search endpoint that invokes Sherlock; Pydantic username validator applied here.
- `api/routes/health.py` — `/health` and `/health/memory` (admin-gated). Add Thordata metrics here, same admin gate pattern.
- `api/orchestrator.py` — Global `Semaphore(5)` + `OathNet=3`. Sherlock outbound respects this (no change required).
- `modules/oathnet_client.py` — Reference pattern for httpx.AsyncClient + admin endpoint integration. NOT proxied.

### Codebase Maps (background)
- `.planning/codebase/STACK.md`
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/CONVENTIONS.md`
- `.planning/codebase/CONCERNS.md`

### Prior Phase Decisions (still binding)
- Phase 06 (F4): body cap 512KB global — Sherlock-specific 256KB is additional, never above 512KB.
- Phase 14 (D-06): Sherlock 4 fields ceiling, no scrapers — Phase 16 does not expand displayed fields.
- Phase 15 (D-01): `schemas.py` LEAF — only `re` + `pydantic`. New Pydantic username validator goes there or in route module.

### External (Thordata)
- Thordata docs (researcher: confirm sticky session syntax via Context7 or web fetch). Provider portal `thordata.net`. The `.env` URL format is `http://td-customer-USER:PASS@HOST:PORT`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `httpx.AsyncClient` already configured with `headers`, `timeout`, `follow_redirects`, `verify=False`, `limits` — proxy injection point is `proxies=` kwarg on the same constructor (`httpx.AsyncClient(proxies=THORDATA_PROXY_URL, ...)`).
- `PLATFORMS` dict structure is extensible — adding `negative_markers: list[str]` per entry is non-breaking.
- `PlatformResult` dataclass has `error: Optional[str]` field — `proxy_unavailable` slots in cleanly.
- `SherlockResult.found / not_found / errors` triage already classifies — extend with `likely: list[PlatformResult]` for new state.
- `loguru` available project-wide (CLAUDE.md prescribes it). Use for budget WARNING / circuit-breaker CRITICAL.
- `psutil` already in stack (used in `/health`) — useful if budget tracker needs anything beyond pure counters.

### Established Patterns
- `api/config.py` is the ONLY place env vars are loaded (`os.getenv` + `dotenv.load_dotenv`). Phase 15 D-01 enforces leaf rule.
- Admin-gated routes: `Depends(get_admin_user)` + `RL_ADMIN_LIMIT` slowapi decorator. Existing `/health/memory` is the template.
- Username hashing for logs: SHA256 truncated 8 chars (CLAUDE.md `target_hash={hash(target)}` pattern — upgrade to SHA256 for non-collision).
- Outbound HTTP: `httpx.AsyncClient` with explicit `timeout` (Phase 11 consolidation, no `requests` / `aiohttp`).
- Test pattern: `respx` for httpx mocking, `aiosqlite` `:memory:` fixture (CLAUDE.md test section + Phase 04 baseline).

### Integration Points
- **Search endpoint** (`api/routes/search.py`) → invokes `sherlock_wrapper.search_username(username)` → Sherlock issues 25 outbound requests via Thordata.
- **Lifespan startup** (`api/main.py`) → adds Thordata health check after JWT validation, before route registration.
- **`/health` admin route** (`api/routes/health.py`) → reads budget tracker module-level counters.
- **Budget circuit breaker** → search endpoint checks budget BEFORE calling Sherlock; raises 503 if budget exhausted.
- **Frontend `static/js/render.js`** → consumes new `state` field on per-platform result; renders `Unverified` badge for `state === "likely"`.

### Creative Options Enabled
- Budget tracker can live as module-level globals in `sherlock_wrapper.py` (simplest) OR as a small `api/budget.py` (testable in isolation). Decision deferred to Claude's discretion.
- `negative_markers` per platform can be lazy-loaded from a JSON file (`modules/sherlock_negatives.json`) for hot-reload OR inlined in `PLATFORMS` dict. Inline is simpler; JSON if researcher finds 100+ markers per platform (unlikely for 25 sites).

</code_context>

<specifics>
## Specific Ideas

- User configured `THORDATA_PROXY_URL` in `.env` already. Format confirmed compatible with httpx `proxies=` kwarg.
- User explicitly invoked CLAUDE.md "Não Confie no Frontend" rule — security hardening section is non-negotiable, applies to all 15 D-H decisions above.
- Caveman-mode discussion — user said "faça o melhor, estou sem ideias, ache soluções" → Claude locked recommended defaults across Areas 2-6.
- Sherlock currently `prefer_cli=False` default — Phase 16 does NOT change CLI fallback strategy, focuses on internal async engine which is the production code path.

</specifics>

<deferred>
## Deferred Ideas

- **Migrate to upstream Sherlock `data.json` (300+ platforms)** — would inflate UI density, bandwidth, regresses Phase 14 D-06 (4-field ceiling). Revisit in dedicated v4.2+ phase if user demand exists.
- **Persistent Thordata budget across restarts** — current in-memory counter resets on container restart. Acceptable trade-off; if abuse pattern emerges, persist counter to SQLite via existing write queue. Track for v4.2.
- **Per-platform proxy bypass list** — some platforms (GitHub, GitLab) rarely block DO IPs. Could skip proxy for those to save Thordata bandwidth. Deferred — premature optimization until budget pressure observed.
- **CLI fallback through proxy** — `subprocess.run(["sherlock", ...])` with proxy env vars. Out of scope; current `prefer_cli=False` default makes this dead code.
- **WebSocket / SSE live progress for Sherlock checks** — UX improvement orthogonal to FP/proxy work.
- **Confidence model trained on real FP data** — current heuristic (40/40/20 weights) is opinionated. Future: collect labeled FP/TP data → tune weights or replace with small ML classifier. Long-term, deferred.

</deferred>

---

*Phase: 16-sherlock-false-positive-filter-thordata-proxy-integration*
*Context gathered: 2026-04-29*
