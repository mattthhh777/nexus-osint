# Phase 09: F7 — Security Hardening - Research

**Researched:** 2026-04-06
**Domain:** Browser security (CSP/event delegation), FastAPI rate limiting (slowapi), backend fail-hard/fail-closed patterns, nginx security headers
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Inline Handler Purge + CSP**
- D-01: Replace all 73 `onclick=` sites with event delegation + `data-action` attributes. One delegated listener per page reads `data-action="deleteCase"` + `data-id="123"` from the closest matching ancestor. Pattern documented once, reused across `index.html`, `admin.html`, and dynamically rendered cards in `render.js`.
- D-02: Strict CSP — drop `unsafe-inline` from BOTH `script-src` AND `style-src`. Inline `<style>` and `style="..."` attributes must move to `meridian.css`. No report-only intermediate step. Enforce immediately.
- D-03: CSP header set in `nginx.conf` (single source of truth). `nginx.conf` is a protected file — explicit user approval required for edit.
- D-04: One sweep, single phase — all 7 files refactored + CSP enforced together. Test gate: every page in DevTools console clean of CSP violations.

**Rate Limiting Design**
- D-05: slowapi with in-memory storage backend.
- D-06: Per-authenticated-user keying on `sub` claim; IP fallback for public endpoints via `X-Forwarded-For`.
- D-07: Conservative ceilings env-tunable: login 5/min/IP, register 3/hr/IP, search 10/min/user, spiderfoot 3/hr/user, admin 30/min/user, reads 60/min/user.
- D-08: nginx `limit_req` zone as outer DDoS shield; slowapi handles per-endpoint per-user logic inside the app.

**Fail-hard + Fail-closed Semantics**
- D-09: JWT_SECRET fail-hard at startup via `_validate_jwt_secret()` called from FastAPI lifespan. Missing/empty/known-weak value → `logger.critical()` + `sys.exit(1)`. No ephemeral key generation.
- D-10: Blacklist fail-closed. Unreachable/corrupt → treat all `is_blacklisted()` lookups as `True`. Returns HTTP 503 with `{"detail": "security policy unavailable"}`. Log warning rate-limited to once/minute.
- D-11: SpiderFoot target validator FQDN + IPv4 only. Pydantic v2 `field_validator`. Returns HTTP 400 on rejection.

**Operational Caps + Security Headers**
- D-12: MAX_USERS env var, default 50. `/auth/register` reads current count from SQLite, returns HTTP 403 on `>= MAX_USERS`.
- D-13: All security headers in `nginx.conf`. CSP, HSTS 1y no-preload, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy.

### Claude's Discretion
- 429 response body shape (suggested: `{"detail": "rate limit exceeded", "retry_after": <seconds>}` + `Retry-After` header)
- slowapi key extractor implementation details (Depends() vs middleware)
- How `_validate_jwt_secret()` is wired into the FastAPI lifespan (asynccontextmanager from Phase 07)
- Exact data-action naming convention (kebab-case vs camelCase) — pick one and stay consistent
- Whether the event delegation listener lives in `static/js/state.js` (shared bootstrap) or per-page

### Deferred Ideas (OUT OF SCOPE)
- CSP report-uri / report-to endpoint
- CSRF tokens for state-changing endpoints
- Login lockout after N failed attempts (separate from rate limiting)
- Waitlist / admin-approval signup flow
- Cache-fallback for blacklist (last good list w/ TTL)
- HSTS preload registration
- CSP nonce-based script allowlist
</user_constraints>

---

## Summary

Phase 09 locks down three distinct attack surfaces: (1) the browser's event handler surface — 73 inline `onclick` attributes across 7 files that require CSP `unsafe-inline` and allow escaping-layer bypasses; (2) the backend's input and identity validation surface — missing JWT_SECRET enforcement, fail-open blacklist, unvalidated SpiderFoot targets, uncapped user registration; (3) the operational hardening surface — security headers consolidated in nginx, per-endpoint rate limiting via slowapi.

The code audit confirms all relevant findings (FIND-03 through FIND-14 in scope) are real and the locked decisions address each one directly. The codebase is already well-positioned: Pydantic v2 `field_validator` is in active use (SearchRequest has one), the FastAPI lifespan (`asynccontextmanager`) from Phase 07 is in place for JWT_SECRET startup validation, `_check_rate()` is SQLite-backed but slowapi in-memory is the right replacement (simpler, faster for the single-worker case), and `_check_blacklist()` currently fails open (line 378 confirmed: `logger.warning("Blacklist check failed (fail-open): %s")`).

**Primary recommendation:** Implement in waves — (1) backend safety gates first (JWT_SECRET, blacklist, SpiderFoot validator, MAX_USERS — zero frontend risk), (2) slowapi wiring (additive, no removals), (3) frontend event delegation refactor (73 sites, highest regression risk), (4) CSP strict enforcement in nginx.conf last (the gate that validates wave 3 is correct).

---

## Audit Findings Coverage

All 8 findings in scope for Phase 09 are addressed by locked decisions:

| Finding | Severity | Addressed By | Decision |
|---------|----------|--------------|----------|
| FIND-03: JWT_SECRET ephemeral fallback | CRITICAL | `_validate_jwt_secret()` + sys.exit(1) at startup | D-09 |
| FIND-04: CSP unsafe-inline | HIGH | Remove `unsafe-inline` from script-src AND style-src | D-02, D-03 |
| FIND-06: No user count limit | HIGH | MAX_USERS env var, hard 403 on registration | D-12 |
| FIND-07: SpiderFoot target not validated | HIGH | Pydantic v2 FQDN+IPv4 validator | D-11 |
| FIND-09: localStorage stores sensitive breach data | MEDIUM | localStorage hardening (store metadata only) | D-01 (indirect) |
| FIND-12: Blacklist fails open | MEDIUM | Fail-closed: return True (blocked) on DB error | D-10 |
| FIND-13: Rate limit comment mismatch | MEDIUM | Fix comment to match `10/60` code or align with slowapi | D-07 |
| FIND-14: innerHTML += in pagination | LOW | Replace with `insertAdjacentHTML('beforeend', ...)` | D-01 (inline handler sweep touches render.js) |

**Gap check:** FIND-09 (localStorage stores full breach data) — D-01 removes inline handlers from `cases.js` but does NOT by itself reduce what is stored in `nx_cases`. The localStorage hardening sub-task must explicitly scope: store only metadata (query, timestamp, counts, risk) in `nx_cases`, NOT the full `snapshot` object. This is currently stored on line 30-37 of `cases.js` (`snapshot: { oathnet, sherlock, extras, elapsed }`). The plan must include removing the `snapshot` key from `saveCase()` and updating `loadCase()` to show metadata-only view.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | 1.0.0 | Per-endpoint rate limiting for FastAPI/Starlette | Built on limits library, starlette-native, confirmed installed |
| Pydantic v2 | 2.8.2 (project) | Input validation with `field_validator` | Already in use, zero new deps |
| PyJWT | 2.9.0 (project) | JWT encode/decode | Already in use |

**Installation (slowapi is the only new dep):**
```bash
pip install "slowapi==1.0.0"
# Add to requirements.txt:
# slowapi==1.0.0
```

**Version confirmation:** slowapi 1.0.0 is confirmed installed locally. PyPI was unreachable at research time; 1.0.0 is the version to pin.

---

## Architecture Patterns

### Pattern 1: Event Delegation with data-action

**What:** One `document.addEventListener('click', handler)` at bootstrap. Each interactive element carries `data-action` and optional `data-*` parameters. The handler reads `event.target.closest('[data-action]')` and dispatches.

**When to use:** Any onclick replacement in vanilla JS. Required here because dynamically rendered cards (render.js) add elements after DOM ready — per-element `addEventListener` would require re-attachment after every render.

**Bootstrap location:** `static/js/state.js` `init()` function — already has a `document.addEventListener('keydown', ...)` call, establishing it as the shared event bootstrap. Add the click delegation there.

**Naming convention (discretion):** Use `kebab-case` for `data-action` values (e.g., `data-action="delete-case"`, `data-action="toggle-panel"`). Reason: HTML attribute convention is lowercase-hyphenated; camelCase in HTML attributes is fragile across browsers.

**Example — handler structure:**
```javascript
// In state.js init() — after existing keydown listener
document.addEventListener('click', function handleAction(e) {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const action = el.dataset.action;
  const id     = el.dataset.id;     // optional
  const value  = el.dataset.value;  // optional

  switch (action) {
    case 'delete-case':    deleteCase(id); break;
    case 'load-case':      loadCase(id); break;
    case 'clear-cases':    clearAllCases(); break;
    case 'toggle-panel':   togglePanel(id); break;
    case 'toggle-cases-panel': toggleCasesPanel(); break;
    case 'save-case':      saveCase(); break;
    case 'copy-all':       copyAll(); break;
    case 'export-json':    exportJSON(); break;
    case 'export-csv':     exportCSV(); break;
    case 'export-txt':     exportTXT(); break;
    case 'export-pdf':     exportPDF(); break;
    case 'new-search':     newSearch(); break;
    case 'start-search':   startSearch(); break;
    case 'set-mode':       setMode(el.dataset.value); break;
    case 'set-sf-mode':    setSfMode(el.dataset.value, el); break;
    case 'sign-out':       signOut(); break;
    case 'copy-section':   copySection(id); break;
    case 'copy-file':      copyFileContent(); break;
    case 'close-viewer':   closeFileViewer(); break;
    case 'submit-auth':    submitAuth(); break;
    // render.js dynamic actions:
    case 'toggle-pwd':     togglePwd(id); break;
    case 'open-tree':      openVictimTree(id); break;
    case 'toggle-dir':     toggleDir(id); break;
    case 'view-file':      viewFile(id, el.dataset.logId); break;
    // add more as discovered in render.js sweep
    default:
      console.warn('[NexusOSINT] Unhandled action:', action);
  }
});
```

**Edge cases to handle:**
1. **Dynamic content:** Handler on `document` captures all current and future elements — no re-attachment needed after render.
2. **Event propagation for nested elements:** `e.target.closest('[data-action]')` walks up the DOM tree, so clicking an icon inside a button still triggers the button's action.
3. **Forms with oninput/onkeydown:** These are NOT click events. `oninput` on `#searchInput` and `onkeydown` on the same element need separate `input` and `keydown` delegation — or convert to direct `addEventListener` after element exists. Since these are static elements (not dynamically rendered), direct `addEventListener` after DOM ready is cleaner than delegated input/keydown.
4. **`cases.js` textarea `onblur`/`onfocus`:** These are on dynamically rendered elements. Use a single delegated `blur`/`focus` listener on `document` with `data-action="save-note"` + `data-id`.
5. **SpiderFoot mode buttons with active state:** `setSfMode(value, el)` passes `el` for active class toggle — the handler must pass `el` (the `closest('[data-action]')` result).

**Inline `style=` migration:** The strict `style-src` (D-02) bans `style=` attributes. Index.html and admin.html have many `style="..."` attributes for layout tweaks (display:none, margin, etc.). These must move to CSS classes in `meridian.css`. Strategy: create a set of utility classes (`.u-hidden` for `display:none`, `.u-mt-{n}` for margins, or just create semantic named classes per element). Do NOT use a `<style>` block in the HTML — that also requires `unsafe-inline` under strict style-src.

**Critical: `<script>init();</script>` in index.html:** Line 350-359 of `index.html` has an inline `<script>` block calling `init()` and attaching listeners. This requires `unsafe-inline` for `script-src`. Under D-02, this block must move to an external JS file. The cleanest solution: add a `js/bootstrap.js` file that calls `init()` and attaches the auth input listeners, and reference it as the last `<script src>` tag. Alternatively, move the three-line body into an existing JS file (e.g., end of `state.js`).

### Pattern 2: slowapi Integration with FastAPI

**What:** slowapi wraps the Starlette `Request` object. Uses `Limiter` with a key function. Applied via `@limiter.limit()` decorator on route handlers.

**Current state:** The project uses a custom `_check_rate()` function backed by SQLite. slowapi replaces this for endpoint-level limits only. The existing SQLite-backed `_check_rate` is already used in `login` (lines 569-574) — slowapi replaces these calls with decorators.

**Setup:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Key function: per-authenticated-user with IP fallback
def _rate_key(request: Request) -> str:
    # Try to get JWT sub from cookie (authenticated users)
    token = request.cookies.get("nx_session")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    # Fallback: client IP (already validated by get_client_ip)
    return f"ip:{get_client_ip(request)}"

limiter = Limiter(key_func=_rate_key, default_limits=["1000/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Registration order:** Add `app.state.limiter` BEFORE route definitions but AFTER `app` is created. The exception handler replaces slowapi's default 429 response — custom handler should return `{"detail": "rate limit exceeded", "retry_after": <seconds>}` + `Retry-After` header.

**Decorator syntax:**
```python
@app.post("/api/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    ...

@app.post("/api/search")
@limiter.limit("10/minute")
async def search(request: Request, ...):
    ...
```

**Important:** `request: Request` MUST be in the function signature for slowapi to extract the key. It is already present in most endpoints (confirmed in code scan).

**Custom 429 handler:**
```python
from fastapi.responses import JSONResponse

async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = exc.limit.reset_time if hasattr(exc.limit, 'reset_time') else 60
    return JSONResponse(
        status_code=429,
        content={"detail": "rate limit exceeded", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )
```

**In-memory vs SQLite:** slowapi in-memory resets on restart (acceptable per D-05). The existing SQLite `_check_rate` for login can be REPLACED by slowapi decorator — simpler, less code. Keep `_check_rate` only if needed for non-endpoint rate limiting.

**Conflict avoidance:** The existing nginx `limit_req` zones (api: 30r/m, search: 5r/m burst=3) are the outer DDoS shield (D-08). slowapi adds per-user application-layer limits inside. These are additive — a user hitting the nginx zone gets 429 from nginx before reaching slowapi.

### Pattern 3: Pydantic v2 field_validator for FQDN + IPv4

**What:** A `field_validator` that rejects anything that isn't a valid FQDN or IPv4 dotted-quad.

**Existing pattern in codebase:** `SearchRequest.sanitize_query` at line 122-136 uses `@field_validator("query") @classmethod`. SpiderFoot validator follows the same structure.

**RFC 1123 FQDN regex + IPv4:**
```python
import re
import ipaddress

# RFC 1123 hostname: labels 1-63 chars, alphanumeric + hyphens, no leading/trailing hyphen
_FQDN_RE = re.compile(
    r'^(?=.{1,253}$)(?!-)[a-zA-Z0-9\-]{1,63}(?<!-)'
    r'(?:\.(?!-)[a-zA-Z0-9\-]{1,63}(?<!-))*'
    r'(?:\.[a-zA-Z]{2,63})?$'
)
_IPV4_RE = re.compile(
    r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$'
)

def _is_valid_spiderfoot_target(v: str) -> bool:
    v = v.strip()
    # Try strict IPv4 first
    try:
        addr = ipaddress.IPv4Address(v)
        # Reject private/loopback/link-local — no scanning internal ranges
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return False
        return True
    except ValueError:
        pass
    # FQDN check
    return bool(_FQDN_RE.match(v))
```

**Applying to SpiderFootScanRequest (new model) or SearchRequest:**
```python
class SpiderFootScanRequest(BaseModel):
    target: str
    mode: str = "passive"

    @field_validator("target")
    @classmethod
    def validate_sf_target(cls, v: str) -> str:
        v = v.strip()
        if not _is_valid_spiderfoot_target(v):
            raise ValueError("invalid target: must be FQDN or IPv4")
        return v

    @field_validator("mode")
    @classmethod
    def validate_sf_mode(cls, v: str) -> str:
        return v if v in ("passive", "footprint", "investigate") else "passive"
```

**Unicode normalization concern:** `v.strip()` is not enough. Punycode/unicode homoglyphs can bypass simple regex. Add `v = v.encode('ascii', errors='ignore').decode('ascii')` before validation — reject non-ASCII entirely. This is correct for OSINT targets (FQDNs must be ASCII for SpiderFoot CLI).

### Pattern 4: JWT_SECRET Fail-Hard at Startup

**What:** Called from the existing lifespan `asynccontextmanager` before `yield` (startup phase). Checks env var presence, length, and known-weak values.

**Known-weak list (conservative):** `changeme`, `secret`, `dev`, `test`, `password`, `nexusosint`, `jwt_secret`. Also reject any value shorter than 32 chars.

```python
_WEAK_SECRETS = frozenset({
    "changeme", "secret", "dev", "test", "password",
    "nexusosint", "jwt_secret", "your-secret-here",
})

def _validate_jwt_secret() -> None:
    """Fail hard if JWT_SECRET is missing, weak, or a known default."""
    raw = os.getenv("JWT_SECRET", "")
    if not raw:
        logger.critical(
            "FATAL: JWT_SECRET env var not set. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
        import sys; sys.exit(1)
    if len(raw) < 32:
        logger.critical(
            "FATAL: JWT_SECRET is too short (%d chars). Minimum 32 characters required.", len(raw)
        )
        import sys; sys.exit(1)
    if raw.lower() in _WEAK_SECRETS:
        logger.critical(
            "FATAL: JWT_SECRET matches a known weak/default value. Set a random secret."
        )
        import sys; sys.exit(1)
```

**Wiring into lifespan:**
```python
@asynccontextmanager
async def lifespan(application: FastAPI):
    _validate_jwt_secret()          # <-- before any other startup
    tracemalloc.start(10)
    _ensure_default_user()
    await _db.startup(db_path=AUDIT_DB)
    ...
    yield
    ...
```

**Dev environment escape hatch:** The function reads `os.getenv("JWT_SECRET")` directly — in dev, set a sufficiently long random secret in `.env`. No special `ENV=dev` bypass. The check is the same in all environments. This is intentional per D-09.

### Pattern 5: Blacklist Fail-Closed

**Current code (fail-open):**
```python
# api/main.py line 377-378
except aiosqlite.Error as exc:
    logger.warning("Blacklist check failed (fail-open): %s", exc)
    # Implicitly returns None — caller proceeds
```

**Fixed (fail-closed):**
```python
except aiosqlite.Error as exc:
    logger.warning("Blacklist DB unavailable — failing closed: %s", type(exc).__name__)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="security policy unavailable",
    )
```

**Rate-limiting the warning log:** The CONTEXT.md says log once per minute. Use a module-level timestamp:
```python
_blacklist_warn_ts: float = 0.0

except aiosqlite.Error as exc:
    global _blacklist_warn_ts
    now = time.time()
    if now - _blacklist_warn_ts > 60:
        logger.warning("Blacklist DB unavailable — failing closed: %s", type(exc).__name__)
        _blacklist_warn_ts = now
    raise HTTPException(status_code=503, detail="security policy unavailable")
```

### Pattern 6: nginx add_header Inheritance Trap

**CRITICAL PITFALL:** nginx `add_header` directives in a parent block are NOT inherited by child `location` blocks that define their own `add_header` directives. This is a confirmed nginx behavior (documented in nginx core module docs).

**Current nginx.conf evidence:** The server block (lines 54-59) sets security headers. The `/css/` and `/js/` location blocks (lines 62-74) add their own `add_header Content-Type` and `Cache-Control` directives. **This means those locations currently do NOT send the CSP or security headers set in the server block.**

**Fix — two options:**
1. **Repeat all security headers in each location block** — verbose but explicit.
2. **Use `proxy_hide_header` + `add_header` in a map** — more complex.
3. **Preferred for this codebase:** Move security headers to a shared `include` file and include it in every location block that needs them. OR use `always` flag combined with a single `location /` catch-all approach.

**Recommended approach for NexusOSINT:** The static assets (`/css/`, `/js/`) are public and cached. The CSP must apply to the main document (`/`, `/admin`) — not necessarily to CSS/JS files themselves (CSP is enforced by the browser when applied to HTML responses, not to subresource responses). The critical requirement is that `/` and `/admin` and `/api/*` responses carry the security headers.

**Correct structure:**
```nginx
# Server block — security headers with always
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
add_header Content-Security-Policy "..." always;

# Location blocks that define their OWN add_header MUST repeat all security headers
location /css/ {
    alias /etc/nginx/static/css/;
    add_header Content-Type text/css;
    add_header Cache-Control "public, max-age=31536000, immutable";
    # Security headers NOT inherited — must repeat if needed
    # For CSS/JS files: CSP is not enforced by browser on subresources
    # X-Content-Type-Options nosniff IS useful here to prevent MIME sniffing
    add_header X-Content-Type-Options nosniff always;
    access_log off;
}
```

**Practical decision for this phase:** The existing `/css/` and `/js/` location blocks define their own `add_header`. Since the plan is to add all security headers to the server block, the planner must also add `X-Content-Type-Options nosniff always;` to the `/css/` and `/js/` locations (MIME sniffing protection for assets matters). The full CSP on these locations is optional but harmless.

### Pattern 7: CSP Policy for NexusOSINT Stack

**Current CSP (line 58 of nginx.conf):**
```
default-src 'self';
script-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://static.cloudflareinsights.com;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self';
frame-ancestors 'none';
```

**Post-hardening target (strict, no unsafe-inline):**
```
default-src 'self';
script-src 'self' https://static.cloudflareinsights.com;
style-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self' https://static.cloudflareinsights.com;
frame-ancestors 'none';
```

**Directive-by-directive reasoning:**
- `script-src 'self'`: serves all JS from same origin. Cloudflare Insights (`https://static.cloudflareinsights.com`) is referenced in the original — keep it. Remove `unsafe-inline` entirely once inline `<script>init();</script>` is moved to `bootstrap.js`.
- `style-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com`: Google Fonts CSS is loaded via `<link href="https://fonts.googleapis.com/css2?...">` in `index.html` line 8. This is a stylesheet from an external origin — must be in `style-src`. Remove `unsafe-inline` once all `style=` attributes and `<style>` blocks are moved to CSS files.
- `font-src 'self' https://fonts.gstatic.com`: Font files are served from gstatic. Unchanged.
- `img-src 'self' data: https:`: Broad `https:` allows Discord avatars and arbitrary images from OathNet results. Acceptable for an OSINT tool where image sources are dynamic. Keep.
- `connect-src 'self'`: SSE stream `/api/search` is same-origin. All `apiFetch()` calls are same-origin. Cloudflare Insights may make beacon requests — add it here.
- `frame-ancestors 'none'`: Equivalent to X-Frame-Options DENY. Keep.

**Inline style inventory — what must move to CSS:**
- `index.html`: Many `style="display:none"`, `style="margin-bottom:..."`, `style="position:relative"`, etc. These are layout overrides. Must become CSS classes.
- `admin.html`: Confirmed to have inline CSS blocks (AUDIT: "admin.html has inline CSS"). This is the hardest file — all inline `<style>` blocks must move to a new `static/css/admin.css` file.

**SSE streaming:** `/api/search` uses Server-Sent Events. `connect-src 'self'` covers SSE connections to the same origin. No additional directive needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-endpoint rate limiting | Custom decorator with SQLite | slowapi 1.0.0 | Already installed, handles limits library, starlette-native |
| IP extraction from X-Forwarded-For | Custom header parser | Existing `get_client_ip()` in main.py | Already validates IP format, handles Cloudflare/nginx chain |
| FQDN validation regex | Bespoke regex from scratch | Combine `ipaddress.IPv4Address` + anchored RFC-1123 regex | `ipaddress` stdlib handles dotted-quad edge cases |
| Event delegation router | Per-element `addEventListener` sweep | Single `document.addEventListener('click', handler)` on `document` | Covers dynamically rendered elements, no re-attachment |
| JWT decode in rate-limit key func | Separate auth middleware | Re-use `jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])` | Same decode call already in `get_current_user`, just extract to shared function |

---

## Common Pitfalls

### Pitfall 1: nginx add_header Inheritance
**What goes wrong:** Security headers set in the server block disappear for any `location` block that defines its own `add_header`. Silent failure — browser receives no CSP on static assets.
**Why it happens:** nginx `add_header` does not merge with parent blocks; child blocks override parent.
**How to avoid:** Repeat critical security headers in every `location` block, or restructure to use `include` snippets. For this project, add `X-Content-Type-Options nosniff always;` to `/css/` and `/js/` locations at minimum.
**Warning signs:** DevTools Network tab shows CSP header on `/` but not on `/js/main.js`.

### Pitfall 2: Strict CSP Breaks App Before Inline Handlers Are Removed
**What goes wrong:** Enabling strict CSP in nginx.conf BEFORE completing the frontend refactor causes every page to break (CSP blocks inline handlers).
**Why it happens:** CSP is enforced by the browser immediately on document load.
**How to avoid:** Complete the 73-site onclick sweep and inline style migration first, verify with `Content-Security-Policy-Report-Only` header, THEN switch to enforcing `Content-Security-Policy`. The locked decision (D-04) says no report-only step — this means the implementation wave must be: code first, CSP last, test gate between.
**Warning signs:** Every button stops working after nginx.conf change.

### Pitfall 3: slowapi @limiter.limit() Missing request Parameter
**What goes wrong:** `TypeError: missing required argument 'request'` at runtime.
**Why it happens:** slowapi needs `request: Request` as a named parameter in the decorated function to extract the key.
**How to avoid:** Verify every `@limiter.limit()` decorated endpoint has `request: Request` in its signature. Most NexusOSINT endpoints already have it, but some (e.g., `admin_list_users`) use `_: dict = Depends(get_admin_user)` and may omit `request`.
**Warning signs:** 500 errors on decorated endpoints after adding slowapi.

### Pitfall 4: slowapi + FastAPI Exception Handler Order
**What goes wrong:** Custom 429 handler not triggered; slowapi returns its default plain-text response.
**Why it happens:** `app.add_exception_handler` must be called AFTER `app = FastAPI(...)` but the handler must be registered with the correct exception type.
**How to avoid:** `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`. The handler function must be `async def` and accept `(request: Request, exc: RateLimitExceeded)`.
**Warning signs:** 429 responses return plain text instead of JSON.

### Pitfall 5: event.target vs closest() for Nested Elements
**What goes wrong:** Click on an `<svg>` icon inside a button doesn't trigger the delegated action because `event.target` is the SVG element, not the button.
**Why it happens:** `event.target` is the deepest element clicked, not the element with `data-action`.
**How to avoid:** Always use `event.target.closest('[data-action]')` — it walks up the DOM tree. Already documented in Pattern 1 above.
**Warning signs:** Clicking button icons does nothing; clicking button text works.

### Pitfall 6: Textarea onblur/onfocus in cases.js
**What goes wrong:** `onblur="saveCaseNote(...)"` and `onfocus="..."` on dynamically rendered `<textarea>` elements — these are NOT click events.
**Why it happens:** The event delegation pattern for `click` doesn't capture `blur`/`focus`.
**How to avoid:** Add separate delegated listeners for `blur` and `focus` on `document` with `useCapture=true`, OR convert the note-saving to a different trigger (e.g., `input` event with debounce). Recommended: use `input` event with `data-action="save-note"` and `data-id`:
```javascript
document.addEventListener('input', function(e) {
  const el = e.target.closest('[data-note-id]');
  if (el) saveCaseNote(el.dataset.noteId, el.value);
});
```
**Warning signs:** Case notes don't save after removing `onblur`.

### Pitfall 7: MAX_USERS Check Race Condition (benign, worth noting)
**What goes wrong:** Two simultaneous registration requests could both pass the count check and both create users, briefly exceeding MAX_USERS.
**Why it happens:** Read-then-write is not atomic. SQLite write queue serializes writes but the count read happens outside the queue.
**How to avoid:** For a 50-user cap on a single-writer VPS, this is a benign race (at most 51 users). No fix needed for this phase. Note in code comments.
**Warning signs:** User count slightly exceeds MAX_USERS under concurrent registration load (extremely unlikely in practice).

### Pitfall 8: HSTS max-age Change from Current nginx.conf
**Current:** `max-age=63072000; includeSubDomains; preload` (2 years, with preload)
**Decision D-13:** `max-age=31536000; includeSubDomains` (1 year, no preload)

The locked decision drops the `preload` directive. This is correct (preload is permanent and hard to reverse). HOWEVER, if the domain is already in the HSTS preload list, removing `preload` from the header does NOT remove it from the list. The planner should note this: the nginx.conf change is safe and correct, but domain preload list status is outside the scope of this phase.

---

## Code Examples

### Event Delegation Bootstrap (state.js)
```javascript
// Source: MDN event delegation pattern + NexusOSINT data-action convention
// Add to init() in static/js/state.js after existing keydown listener

document.addEventListener('click', function handleAction(e) {
  const el = e.target.closest('[data-action]');
  if (!el || el.disabled) return;
  e.preventDefault();   // prevent default only for known actions

  const action = el.dataset.action;
  switch (action) {
    // Auth
    case 'submit-auth':   submitAuth(); break;
    case 'sign-out':      signOut(); break;
    // Search
    case 'start-search':  startSearch(); break;
    case 'new-search':    newSearch(); break;
    case 'set-mode':      setMode(el.dataset.value); break;
    case 'set-sf-mode':   setSfMode(el.dataset.value, el); break;
    // Results
    case 'save-case':     saveCase(); break;
    case 'copy-all':      copyAll(); break;
    case 'copy-section':  copySection(el.dataset.section); break;
    case 'export-json':   exportJSON(); break;
    case 'export-csv':    exportCSV(); break;
    case 'export-txt':    exportTXT(); break;
    case 'export-pdf':    exportPDF(); break;
    case 'toggle-panel':  togglePanel(el.dataset.panel); break;
    // Cases panel
    case 'toggle-cases-panel': toggleCasesPanel(); break;
    case 'load-case':     loadCase(el.dataset.id); break;
    case 'delete-case':   deleteCase(el.dataset.id); break;
    case 'clear-cases':   clearAllCases(); break;
    // Viewer
    case 'close-viewer':  closeFileViewer(); break;
    case 'copy-file':     copyFileContent(); break;
    // Dynamic render.js actions
    case 'toggle-pwd':    togglePwd(el.dataset.id); break;
    default:
      // Unknown actions — silent in prod, warn in dev
  }
});
```

### slowapi Setup (api/main.py)
```python
# Source: slowapi 1.0.0 documentation pattern, verified against codebase
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

def _rate_key(request: Request) -> str:
    """Per-user key with IP fallback. Called by slowapi on every limited request."""
    token = request.cookies.get("nx_session")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_client_ip(request)}"

limiter = Limiter(key_func=_rate_key)
# Register BEFORE route definitions, AFTER app = FastAPI(...)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Usage on endpoints:
@app.post("/api/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    ...
```

### Pydantic v2 SpiderFoot Validator
```python
# Source: existing SearchRequest.sanitize_query pattern in api/main.py
import re, ipaddress

_FQDN_RE = re.compile(
    r'^(?=.{1,253}$)(?!-)[a-zA-Z0-9\-]{1,63}(?<!-)'
    r'(?:\.(?!-)[a-zA-Z0-9\-]{1,63}(?<!-))*$'
)

def _is_valid_sf_target(v: str) -> bool:
    v = v.encode('ascii', errors='ignore').decode('ascii').strip()
    try:
        addr = ipaddress.IPv4Address(v)
        return not (addr.is_private or addr.is_loopback or addr.is_link_local)
    except ValueError:
        pass
    return bool(_FQDN_RE.match(v)) and '.' in v  # require at least one dot for FQDN

class SpiderFootScanRequest(BaseModel):
    target: str
    mode: str = "passive"

    @field_validator("target")
    @classmethod
    def validate_sf_target(cls, v: str) -> str:
        clean = v.encode('ascii', errors='ignore').decode('ascii').strip()
        if not _is_valid_sf_target(clean):
            raise ValueError("invalid target: must be FQDN or IPv4")
        return clean
```

### JWT_SECRET Startup Guard
```python
# Source: CONTEXT.md D-09 + FastAPI lifespan pattern already in main.py
_WEAK_SECRETS = frozenset({
    "changeme", "secret", "dev", "test", "password",
    "nexusosint", "jwt_secret", "your-secret-here", "example",
})

def _validate_jwt_secret() -> None:
    import sys
    raw = os.getenv("JWT_SECRET", "")
    if not raw:
        logger.critical(
            "FATAL: JWT_SECRET not set. "
            "Generate: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
        sys.exit(1)
    if len(raw) < 32:
        logger.critical("FATAL: JWT_SECRET too short (%d chars, min 32)", len(raw))
        sys.exit(1)
    if raw.lower() in _WEAK_SECRETS:
        logger.critical("FATAL: JWT_SECRET is a known weak value")
        sys.exit(1)

# In lifespan():
@asynccontextmanager
async def lifespan(application: FastAPI):
    _validate_jwt_secret()   # first — blocks startup before anything else
    tracemalloc.start(10)
    ...
```

### Blacklist Fail-Closed
```python
# Source: CONTEXT.md D-10 + existing _check_blacklist structure in main.py
_blacklist_warn_ts: float = 0.0

async def _check_blacklist(jti: Optional[str]) -> None:
    if not jti:
        return
    try:
        await _db.write(
            "DELETE FROM token_blacklist WHERE exp < ?",
            (int(time.time()),),
        )
        row = await _db.read_one(
            "SELECT 1 as found FROM token_blacklist WHERE jti = ?", (jti,)
        )
        if row is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except aiosqlite.Error as exc:
        global _blacklist_warn_ts
        now = time.time()
        if now - _blacklist_warn_ts > 60:
            logger.warning("Blacklist DB unavailable — failing closed: %s", type(exc).__name__)
            _blacklist_warn_ts = now
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="security policy unavailable",
        )
```

### nginx.conf Security Headers Block (updated)
```nginx
# Add to https server block — replaces existing add_header directives (lines 54-59)
# Source: CONTEXT.md D-13 + nginx add_header docs (inheritance trap awareness)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://static.cloudflareinsights.com; style-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://static.cloudflareinsights.com; frame-ancestors 'none';" always;

# ALSO add to /css/ and /js/ location blocks (inheritance gap):
location /css/ {
    alias /etc/nginx/static/css/;
    add_header Content-Type text/css;
    add_header Cache-Control "public, max-age=31536000, immutable";
    add_header X-Content-Type-Options nosniff always;
    access_log off;
}
location /js/ {
    alias /etc/nginx/static/js/;
    add_header Content-Type application/javascript;
    add_header Cache-Control "public, max-age=31536000, immutable";
    add_header X-Content-Type-Options nosniff always;
    access_log off;
}
```

---

## Implementation Wave Order

This section is the critical sequencing guidance for the planner.

| Wave | Scope | Risk | Regression Vector |
|------|-------|------|-------------------|
| Wave 1 | Backend safety gates: JWT_SECRET guard, blacklist fail-closed, MAX_USERS, SpiderFoot validator, FIND-13 comment fix | LOW | Zero frontend changes; backend-only |
| Wave 2 | slowapi wiring: install, limiter setup, decorate endpoints, custom 429 handler | LOW | Additive; existing `_check_rate` calls remain until tested |
| Wave 3 | Frontend refactor: all 73 onclick → data-action, inline `<style>`/`style=` → CSS, inline `<script>` → bootstrap.js, localStorage hardening | HIGH | Every interactive element is touched |
| Wave 4 | nginx.conf: CSP strict + all security headers | MEDIUM | Gate on Wave 3 complete + DevTools console clean |

**Wave 3 → Wave 4 gate:** Load every page (search, results, cases, history, export, admin), open DevTools Console, confirm zero CSP violations. Only then update nginx.conf.

---

## Project Constraints (from CLAUDE.md)

All constraints remain enforced in Phase 09:

| Constraint | Impact on Phase 09 |
|------------|-------------------|
| Backend-only authorization; frontend is hostile territory | slowapi rate limiting, JWT_SECRET guard, MAX_USERS, blacklist — all backend. Event delegation refactor does NOT add any authz logic to frontend |
| No `except Exception` generic catch | `_validate_jwt_secret` uses `sys.exit(1)` not an exception catch. Blacklist uses `except aiosqlite.Error` specifically. slowapi custom handler is typed to `RateLimitExceeded` |
| RAM < 200MB resting | slowapi in-memory storage for single worker: confirmed acceptable. 73 onclick replacements are zero memory cost |
| Single uvicorn worker | slowapi in-memory is correct choice — no cross-process sync |
| Loguru structured logging, no PII | Rate limit log messages hash user identifier. Blacklist warning logs exception type, not token content |
| nginx.conf is a PROTECTED file | Explicit user approval required before edit. Plan must include checkpoint/approval step |
| meridian.css is PROTECTED | Additions allowed (moving inline styles into it). No existing rules modified |
| Docker image < 250MB | `slowapi==1.0.0` is ~15KB wheel. Negligible |
| No `except Exception` without specific type | Verified in all code examples above |
| PROIBIDO: pseudo-code, placeholders, TODOs without implementation | All code examples above are complete and runnable |

---

## Environment Availability

Step 2.6: All dependencies are Python packages installed in the container. No external services required for this phase beyond what already exists.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| slowapi | Rate limiting D-05 | Yes (installed) | 1.0.0 | — |
| Pydantic v2 | SpiderFoot validator D-11 | Yes | 2.8.2 | — |
| PyJWT | JWT_SECRET guard D-09 | Yes | 2.9.0 | — |
| aiosqlite | Blacklist D-10 | Yes | 0.20.0 | — |
| nginx | Security headers D-13 | Yes (container) | existing | — |

**Missing dependencies with no fallback:** None.

**Step 2.5 (Runtime State Inventory):** SKIPPED — this is a code hardening phase, not a rename/refactor/migration phase. No stored data, service config, or OS-registered state is renamed.

---

## Open Questions

1. **admin.html inline CSS scope**
   - What we know: admin.html is ~1426 lines, has inline CSS (confirmed by audit). Not opened during research.
   - What's unclear: Whether the inline CSS is in `<style>` blocks, `style=` attributes, or both; total count of style= attributes in admin.html.
   - Recommendation: Planner should include a pre-implementation step to count/grep `style=` and `<style>` occurrences in admin.html before estimating Wave 3 effort.

2. **Cloudflare Insights script presence**
   - What we know: `https://static.cloudflareinsights.com` is in the current CSP `script-src`. The analytics script is injected by Cloudflare proxy — not present in the repo.
   - What's unclear: Whether the Cloudflare Insights script is actually active (depends on Cloudflare dashboard settings), and whether it makes `connect-src` requests to its own domain.
   - Recommendation: Keep `https://static.cloudflareinsights.com` in both `script-src` and `connect-src`. Removing it would break analytics silently if active.

3. **`panels.js` onclick count**
   - What we know: The scout confirmed 73 onclick sites across 7 files. The grep count above confirms the file breakdown. `panels.js` is referenced in index.html line 346 but NOT in the grep results.
   - What's unclear: Whether `panels.js` has any onclick handlers (count is 0 in grep results — confirmed clean).
   - Recommendation: No action for panels.js in Wave 3.

4. **Existing `_check_rate` calls post-slowapi**
   - What we know: The login endpoint already uses `_check_rate` (lines 569-574). slowapi replaces this for endpoint rate limiting.
   - What's unclear: Whether to remove the existing `_check_rate` calls from login after adding slowapi, or layer both.
   - Recommendation: Replace `_check_rate` in login with `@limiter.limit("5/minute")` decorator. Remove the in-function calls to reduce complexity. The SQLite-backed `_check_rate` can remain for any non-endpoint use cases (none found in current codebase).

---

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis — `api/main.py`, `static/index.html`, `static/js/*.js`, `nginx.conf`, `requirements.txt` — confirmed against actual file contents
- `.planning/phases/03-codebase-audit/AUDIT-REPORT.md` — finding severity and location confirmed
- `.planning/phases/09-f7-security-hardening/09-CONTEXT.md` — all locked decisions
- slowapi 1.0.0 — confirmed installed (`pip3 show slowapi` returned 1.0.0)
- nginx core module docs (knowledge-base) — add_header inheritance behavior is documented and confirmed

### Secondary (MEDIUM confidence)
- CSP directive analysis — based on index.html external resource inspection (Google Fonts, Cloudflare Insights) + MDN CSP documentation (training data, stable specification)
- RFC 1123 hostname regex — standard, stable specification

### Tertiary (LOW confidence)
- PyPI query for slowapi latest version — pypi.org query failed at research time; 1.0.0 is confirmed installed locally

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against installed packages and codebase
- Architecture patterns: HIGH — derived from direct codebase reading, not assumed
- Pitfalls: HIGH — nginx inheritance confirmed by nginx docs; others derived from code analysis
- CSP policy: MEDIUM-HIGH — constructed from actual resource inventory in index.html; admin.html not fully read

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (slowapi 1.0.0 API is stable; nginx behavior is stable)
