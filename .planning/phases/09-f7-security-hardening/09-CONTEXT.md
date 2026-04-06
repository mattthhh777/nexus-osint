# Phase 09: F7 — Security Hardening - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock down NexusOSINT's security posture across three layers:

1. **Browser-side attack surface** — eliminate all 73 inline `onclick=` handlers across 7 files, ship strict CSP (no `unsafe-inline` for script OR style), enforce in `nginx.conf`.
2. **Backend defenses** — fail-hard secret loading (JWT_SECRET refuses defaults / empty / weak), per-endpoint per-user rate limiting via slowapi, Pydantic input validators on all endpoints (especially SpiderFoot target), fail-closed blacklist semantics.
3. **Operational guardrails** — env-configurable user cap (default 50), security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS) consolidated in `nginx.conf`.

**Out of scope (deferred or done):**
- JWT httpOnly migration (already done in Phase 11)
- Health monitoring / watchdog (Phase 10)
- New CSRF tokens (cookies are SameSite=Strict already; revisit if endpoints accept cross-origin POST)

</domain>

<decisions>
## Implementation Decisions

### Inline Handler Purge + CSP

- **D-01:** Replace all 73 `onclick=` sites with **event delegation + `data-action` attributes**. One delegated listener per page reads `data-action="deleteCase"` + `data-id="123"` from the closest matching ancestor. Pattern is documented once and reused across `index.html`, `admin.html`, and all dynamically rendered cards in `render.js`.
- **D-02:** Ship **strict CSP** in this phase: drop `unsafe-inline` from BOTH `script-src` AND `style-src`. Inline `<style>` and `style="..."` attributes must move to `meridian.css` (or component CSS files). No report-only intermediate step — enforce immediately. Rationale: aligns with CLAUDE.md "fix the frontend, not the CSP".
- **D-03:** CSP header set in **`nginx.conf`** (single source of truth, applied uniformly to static + proxied responses). `nginx.conf` is a protected file — explicit user approval required for the edit, but it's the right architectural home.
- **D-04:** **One sweep, single phase** — all 7 files refactored + CSP enforced together. No half-state where some pages emit CSP violations. Test gate: open every page in the app (search, results, cases, history, export, admin), DevTools console must be clean of CSP errors.

### Rate Limiting Design

- **D-05:** **slowapi with in-memory storage backend.** Single uvicorn worker on 1vCPU means no inter-process sync issues. Counters reset on restart (acceptable for rate-limiting; auth lockouts use a different mechanism). Zero new dependencies, near-zero RAM cost.
- **D-06:** **Per-authenticated-user keying with IP fallback.** Authenticated endpoints key on `sub` claim from JWT. Public endpoints (`/auth/login`, `/auth/register`, `/health`) key on client IP (via `X-Forwarded-For` honoring nginx's `real_ip_module`). Prevents corporate-NAT users from blocking each other.
- **D-07:** **Conservative endpoint ceilings, env-tunable:**
  - `/auth/login`: 5 req/min/IP (lockout-grade)
  - `/auth/register`: 3 req/hour/IP
  - `/api/search`: 10 req/min/user
  - `/api/scan/spiderfoot`: 3 req/hour/user (OathNet quota protection)
  - `/api/admin/*`: 30 req/min/user (admin-only routes)
  - Read endpoints (`/api/cases`, `/api/history`, `/health/*`): 60 req/min/user
  - Each ceiling tunable via `RL_<ENDPOINT>_LIMIT` env var, defaults baked in.
- **D-08:** **Defense-in-depth with nginx.** Keep nginx `limit_req` zone as outer DDoS shield (per-IP, generous: 60 r/s burst 100). slowapi handles per-endpoint per-user logic inside the app. No overlap, no replacement.

### Fail-hard + Fail-closed Semantics

- **D-09:** **JWT_SECRET fail-hard at startup.** On `app.startup`: if env var is missing, empty, or matches a known weak value (`changeme`, `secret`, `dev`, `test`, `password`) → `logger.critical()` + `sys.exit(1)`. **No ephemeral key generation.** Adds a guard function `_validate_jwt_secret()` called from the FastAPI lifespan.
- **D-10:** **Blacklist fail-closed.** If the blacklist source is unreachable, corrupt, or returns an error, treat ALL `is_blacklisted()` lookups as `True` (blocked). The relevant scan endpoint returns HTTP 503 with `{"detail": "security policy unavailable"}`. Logger emits a warning per failure (rate-limited to once per minute to avoid log flood). No cache-fallback layer in this phase — keep it simple, revisit if availability becomes a real problem.
- **D-11:** **SpiderFoot target validator: FQDN + IPv4 only.** Pydantic v2 validator rejects everything else: no IPv6, no CIDR, no URLs, no paths, no spaces, no Unicode tricks. Regex anchored to RFC 1123 hostname OR IPv4 dotted-quad. Returns HTTP 400 with `{"detail": "invalid target: must be FQDN or IPv4"}` on rejection. Covers ~95% of real OSINT use cases with the smallest possible attack surface.

### Operational Caps + Security Headers

- **D-12:** **User cap: hard reject on signup, env-configurable.** `MAX_USERS` env var, default `50`. `/auth/register` reads current count from SQLite first (fast, single-row aggregate), returns HTTP 403 `{"detail": "registration capacity reached"}` if `>= MAX_USERS`. No waitlist, no admin approval flow — those are scope creep for a hardening phase.
- **D-13:** **All security headers in `nginx.conf`.** Single source of truth (matches D-03). Headers shipped together:
  - `Content-Security-Policy: <strict policy from D-02>`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (no preload — avoids permanent registry commitment)
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### Claude's Discretion

- 429 response body shape (suggested: `{"detail": "rate limit exceeded", "retry_after": <seconds>}` + `Retry-After` header)
- slowapi key extractor implementation details (Depends() vs middleware)
- How `_validate_jwt_secret()` is wired into the FastAPI lifespan (asynccontextmanager from Phase 07)
- Exact data-action naming convention (kebab-case vs camelCase) — pick one and stay consistent
- Whether the event delegation listener lives in `static/js/state.js` (shared bootstrap) or per-page

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Charter & Constraints
- `CLAUDE.md` — F7 spec (lines on Security Hardening), exception handling pattern by layer, rate limiting in/out, regras de ouro, file protection rules
- `.planning/PROJECT.md` — F7 status, JWT httpOnly already done in Phase 11 note
- `.planning/REQUIREMENTS.md` — REQ tracking for F7

### Audit Findings (must address)
- `.planning/phases/03-codebase-audit/AUDIT-REPORT.md` — FIND-03, FIND-04, FIND-06, FIND-07, FIND-09, FIND-12, FIND-13, FIND-14
- `.planning/codebase/CONCERNS.md` — open security concerns and resolved entries

### Files in Scope
- `static/index.html` (39 onclick sites) — protected pattern target
- `static/admin.html` (17 onclick sites)
- `static/js/render.js` (10 onclick sites) — dynamic card rendering
- `static/js/cases.js` (2 onclick sites)
- `static/js/export.js` (2 onclick sites)
- `static/js/search.js` (2 onclick sites)
- `static/js/history.js` (1 onclick site)
- `static/js/state.js` — likely home for delegated listener bootstrap
- `nginx.conf` — **PROTECTED** — CSP + all security headers go here
- `api/main.py` — slowapi setup, JWT_SECRET validator, user cap check, SpiderFoot validator wiring
- `modules/spiderfoot_wrapper.py` — target validation entrypoint
- `requirements.txt` — add `slowapi`

### Existing Infrastructure
- `meridian.css` — **PROTECTED** — destination for inline `style=` attribute migration

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FastAPI lifespan (asynccontextmanager)** — installed in Phase 07. `_validate_jwt_secret()` hooks here naturally.
- **Pydantic v2 validators** — already used for input validation across endpoints; SpiderFoot target validator follows existing pattern.
- **`api/db.py` write Queue** — user count read uses standard read connection, no Queue interaction needed.
- **nginx real_ip_module** — already configured (Cloudflare-fronted); slowapi can trust `request.client.host` after nginx rewrite.

### Established Patterns
- **Backend-only authorization** (CLAUDE.md §3) — every authz check in FastAPI; frontend purge of inline handlers does NOT change authz, only DOM event wiring.
- **Single uvicorn worker** — slowapi in-memory storage is safe; no need for distributed limiter.
- **Loguru structured logging, no PII** — rate-limit and fail-closed log messages must hash any user identifier.

### Integration Points
- **Event delegation listener** — bootstraps in `state.js` after DOM ready, single `document.addEventListener('click', handleAction)`.
- **slowapi middleware** — registered after CORS but before route handlers in `api/main.py`.
- **CSP header** — added to nginx server block, before `proxy_pass` directives.

### Constraints from Hardware
- 1 vCPU / 1GB RAM → in-memory rate limit storage is the only sensible choice.
- Single worker → no rate-limit cross-process sync needed.

</code_context>

<specifics>
## Specific Ideas

- Math is direct: prefers single-sweep refactors over staged rollouts when test gate is achievable. D-04 reflects that.
- CLAUDE.md filosofia §3: "frontend é território hostil" — D-09, D-10, D-11 all enforce backend-only validation with no fail-open paths.
- F7 in CLAUDE.md mentions "JWT migration with 24h dual-support window" — superseded by Phase 11 (JWT httpOnly already done). No migration window needed in this phase.
- Test acceptance for D-04: every page in the app loaded, DevTools console clean of CSP violations. This is the ship gate for the inline-handler sweep.

</specifics>

<deferred>
## Deferred Ideas

- **CSP report-uri / report-to endpoint** — collecting violation reports server-side. Useful for production monitoring but adds an endpoint and a storage decision. Defer to v4.1 or Phase 10 (Health Monitoring).
- **CSRF tokens for state-changing endpoints** — currently relying on `SameSite=Strict` cookies. Revisit if any endpoint needs to accept cross-origin POST.
- **Login lockout after N failed attempts** — separate from rate limiting (slowapi covers per-IP throttling). Account-level lockout is a different mechanism (track failed attempts in SQLite). Defer unless brute-force becomes a real signal.
- **Waitlist / admin-approval signup flow** — explicitly out of scope for hardening. Product decision for v5.0.
- **Cache-fallback for blacklist** (last good list w/ TTL) — adds complexity not justified by current availability requirements.
- **HSTS preload registration** — permanent commitment to HTTPS-only via browser hardcode. Only do when 100% sure no subdomain will need HTTP.
- **CSP nonce-based script allowlist** — nicer than strict but requires per-request nonce injection. Not needed once all inline scripts are eliminated.

</deferred>

---

*Phase: 09-f7-security-hardening*
*Context gathered: 2026-04-06*
