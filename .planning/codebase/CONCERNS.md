# Codebase Concerns

**Analysis Date:** 2026-03-25

## Security

### JWT Stored in localStorage [CRITICAL]

- Issue: JWT tokens are stored in `localStorage` via `localStorage.setItem('nx_token', authToken)` in `static/js/auth.js` (line 83). Any XSS vulnerability allows an attacker to steal the token and impersonate any user, including admins.
- Files: `static/js/auth.js` (lines 4, 83-84), `static/js/state.js` (line 9)
- Impact: Full account takeover if combined with any XSS vector. The token grants 24-hour access to all API endpoints including admin functions.
- Fix approach: Migrate to httpOnly cookies set by the backend. The `/api/login` endpoint should return the JWT in a `Set-Cookie` header with `httpOnly`, `Secure`, `SameSite=Strict` flags. Remove all `localStorage.setItem('nx_token', ...)` calls. Update `apiFetch()` to rely on automatic cookie inclusion instead of manual `Authorization` headers.

### XSS via Discord Avatar/Banner URLs [HIGH]

- Issue: In `static/js/render.js` (lines 340-345), Discord avatar and banner URLs from the OathNet API are inserted into `src` and `background-image:url(...)` attributes. While `esc()` is applied, it HTML-escapes but does not validate that the value is actually a URL. A malicious response with a `javascript:` or `data:` URI could bypass the escaping for the `src` attribute. The `onerror` handler on line 341 also creates an inline script execution vector.
- Files: `static/js/render.js` (lines 340-345)
- Impact: If OathNet API returns a crafted avatar_url or banner_url, it could trigger script execution. The `onerror` inline handler is itself a secondary vector.
- Fix approach: Validate URLs against an allowlist of protocols (`https:` only) before inserting into DOM. Use `URL` constructor to parse and reject non-HTTPS schemes. Replace the `onerror` inline handler with a CSS-based fallback or event listener.

### Admin HTML Served Without Server-Side Auth [HIGH]

- Issue: The `/admin` route in `api/main.py` (lines 385-391) serves `static/admin.html` to ANY requester without checking JWT or role. Authentication is performed entirely client-side by the admin page's JavaScript. An attacker can view the admin panel HTML, inspect its structure, and craft direct API calls.
- Files: `api/main.py` (lines 385-391), `static/admin.html`
- Impact: Admin panel structure and API endpoint discovery is trivially available to unauthenticated users. While the admin API endpoints (`/api/admin/*`) do require JWT with admin role (lines 916+), the HTML exposure aids reconnaissance.
- Fix approach: Add `Depends(get_admin_user)` to the `/admin` route handler, or return the HTML only after validating the JWT from the `Authorization` header or cookie. Return 401/403 for unauthenticated or non-admin requests.

### Inconsistent HTML Escaping in render.js [HIGH]

- Issue: The `esc()` function exists in `static/js/utils.js` (lines 42-47) and is used in many places within `static/js/render.js`. However, some template literals use `esc()` only on display text but not on attribute values passed to `onclick` handlers. For example, line 102 passes `escAttr(b.password)` into an onclick handler -- if a password contains certain characters, this could still break out of the attribute context. The `escAttr()` function (lines 49-52) only escapes backslash, single quote, and double quote, missing newlines and other control characters.
- Files: `static/js/render.js` (lines 102, 369, 390, 829), `static/js/utils.js` (lines 49-52)
- Impact: Passwords or other data containing crafted payloads (newlines, backticks) could break out of attribute context in onclick handlers, enabling XSS.
- Fix approach: Eliminate inline `onclick` handlers entirely. Use `data-*` attributes with `esc()` for values and attach event listeners via `addEventListener()`. This removes the need for `escAttr()` altogether.

### Ephemeral JWT Secret Fallback [MEDIUM]

- Issue: When `JWT_SECRET` is not set in the environment, `api/main.py` (lines 44-54) generates a random ephemeral secret using `os.urandom(8)`. This means all active JWT tokens are invalidated on every container restart, and the secret has only 8 bytes of randomness (64 bits) which is below the recommended 256-bit minimum for HS256.
- Files: `api/main.py` (lines 44-54)
- Impact: Users are forced to re-login after every restart. The 64-bit random component (combined with the API key) is weaker than ideal but not trivially exploitable in practice since it also includes the API key in the hash.
- Fix approach: Require `JWT_SECRET` in production (fail hard if not set) or generate a persistent secret stored in the data volume on first run.

## Technical Debt

### Backend Monolith: api/main.py is 1262 Lines [HIGH]

- Issue: `api/main.py` contains ALL backend logic in a single file: configuration, models, rate limiting, user management, JWT auth, audit database, SSE search streaming, admin endpoints, and all API routes. This makes the file extremely difficult to navigate, test, and maintain.
- Files: `api/main.py` (1262 lines)
- Impact: Any change risks breaking unrelated functionality. Code review is painful. Testing individual components is impossible without importing the entire application. New features compound the problem.
- Fix approach: Split into modules:
  - `api/config.py` - Environment variables and constants
  - `api/auth.py` - JWT, user management, password hashing
  - `api/db.py` - SQLite audit log and rate limiting
  - `api/routes/search.py` - SSE search streaming
  - `api/routes/admin.py` - Admin endpoints
  - `api/routes/victims.py` - Victims API proxy
  - `api/dependencies.py` - FastAPI dependencies (get_current_user, etc.)

### OathnetClient Uses Synchronous requests Library [MEDIUM]

- Issue: `modules/oathnet_client.py` uses the synchronous `requests` library (line 26, `import requests`) and creates a `requests.Session()` (line 127). Every API call in the FastAPI async handlers is wrapped in `asyncio.to_thread()` (23 occurrences across `api/main.py`), which consumes a thread from the default executor pool for each concurrent external API call.
- Files: `modules/oathnet_client.py` (lines 26, 127-133), `api/main.py` (lines 588-879)
- Impact: Under concurrent load, the thread pool (default 40 threads in Python) becomes the bottleneck. Each search triggers 3-10 API calls, so as few as 4-13 concurrent users could exhaust the pool. The synchronous session also cannot benefit from HTTP/2 connection multiplexing.
- Fix approach: Rewrite `OathnetClient` to use `httpx.AsyncClient` (httpx is already in `requirements.txt` line 3). Replace all `asyncio.to_thread(client.method)` calls with direct `await client.method()` calls. Use a single shared `httpx.AsyncClient` instance with connection pooling.

### Multiple OathnetClient Instances Per Request [MEDIUM]

- Issue: A new `OathnetClient` instance (and thus a new `requests.Session`) is created on every API call. Found at `api/main.py` lines 580, 1162, 1193, 1225, 1242. Each creates a fresh TCP connection pool.
- Files: `api/main.py` (lines 580, 1162, 1193, 1225, 1242)
- Impact: No connection reuse across requests. Overhead of TCP handshake + TLS negotiation for every search. Wasted memory from abandoned session objects.
- Fix approach: Create a single `OathnetClient` instance at module level or as a FastAPI dependency with `@lru_cache`. After migrating to httpx, use a shared `httpx.AsyncClient` with a lifespan context manager.

### report_generator.py is Dead Code [MEDIUM]

- Issue: `modules/report_generator.py` (839 lines) defines HTML and PDF report generation but is never imported or used anywhere in the application.
- Files: `modules/report_generator.py` (839 lines)
- Impact: 839 lines of unmaintained code that may drift from the current data model. Confusing for developers who may try to use it and find it broken.
- Fix approach: Either integrate it (add export endpoints to `api/main.py` and UI buttons) or delete it. If keeping, add a TODO with a timeline.

### spiderfoot_wrapper.py References Non-Existent Container [LOW]

- Issue: `modules/spiderfoot_wrapper.py` expects SpiderFoot installed at `/opt/spiderfoot` (line 51) and references a `spiderfoot` container. However, `docker-compose.yml` does not include a SpiderFoot service, and the Docker image does not install SpiderFoot. The wrapper also contains Streamlit rendering code (lines 426-530 using `import streamlit as st`) from a previous version.
- Files: `modules/spiderfoot_wrapper.py` (530 lines), `docker-compose.yml`
- Impact: SpiderFoot functionality silently fails. The Streamlit code is legacy dead code. The SPIDERFOOT_URL env var in `docker-compose.yml` (line 24) points to `http://spiderfoot:5001` which does not exist.
- Fix approach: Either add SpiderFoot to `docker-compose.yml` or remove the SpiderFoot module category from the frontend. Remove the Streamlit rendering code. Clean up the unused env var.

### Duplicate HTTP 429 Handling [LOW]

- Issue: In `modules/oathnet_client.py` `_handle()` method, HTTP 429 is checked twice (lines 174 and 179-180) with slightly different error messages.
- Files: `modules/oathnet_client.py` (lines 174, 179-180)
- Impact: Dead code; the second check is unreachable. Minor but indicates copy-paste maintenance issues.
- Fix approach: Remove the duplicate block at lines 179-180.

## CSS/Design System Debt

### Legacy Token Usage Across All CSS Files [HIGH]

- Issue: 341 occurrences of legacy design tokens (`--bg`, `--text`, `--amber`, `--line`, `--mono`, `--sans`, `--r`, `--dur-*`, `--bg2` through `--bg5`, `--red`, `--green`, `--blue`, etc.) are used across all 8 non-token CSS files instead of the Meridian design system tokens (`--color-bg-base`, `--color-text-primary`, `--color-accent`, `--font-data`, `--radius-lg`, `--duration-fast`, etc.). Legacy aliases exist in `static/css/tokens.css` (lines 113-155) as a compatibility bridge.
- Files: All CSS files use legacy tokens:
  - `static/css/cards.css` - 111 occurrences (worst offender)
  - `static/css/panels.css` - 61 occurrences
  - `static/css/components.css` - 51 occurrences
  - `static/css/overlays.css` - 41 occurrences
  - `static/css/tables.css` - 30 occurrences
  - `static/css/layout.css` - 19 occurrences
  - `static/css/reset.css` - 6 occurrences
- Impact: The design system is defined but not adopted. Any future token changes require updating both the Meridian tokens AND the legacy aliases. Two competing naming systems create confusion for developers.
- Fix approach: Systematically replace legacy tokens file-by-file. Start with `layout.css` (fewest occurrences). After all files are migrated, remove the legacy aliases block from `tokens.css` (lines 113-155).

### Hardcoded rgba() Values Instead of Tokens [MEDIUM]

- Issue: 133 hardcoded `rgba()` values across all CSS files, instead of using the design token variables. Examples: `rgba(255,255,255,.07)` appears repeatedly instead of `var(--color-border-subtle)`, `rgba(245,166,35,.22)` instead of `var(--color-accent-border)`, `rgba(0,0,0,.45)` instead of shadow tokens.
- Files: All CSS files, especially:
  - `static/css/tokens.css` - 30 occurrences (legacy shadow block)
  - `static/css/components.css` - 24 occurrences
  - `static/css/cards.css` - 23 occurrences
  - `static/css/overlays.css` - 18 occurrences
- Impact: Color changes require find-and-replace across multiple files. Inconsistent opacity values for the same conceptual color (e.g., amber glow uses `.07`, `.1`, `.14`, `.22`, `.28`, `.35`, `.55` in different places).
- Fix approach: Map common rgba patterns to existing or new tokens. Create additional accent-opacity tokens if needed (e.g., `--color-accent-glow-strong`). Replace systematically per-file.

### Inconsistent border-radius Values [MEDIUM]

- Issue: 69 hardcoded `border-radius` declarations range from `2px` to `14px` and `999px`. The Meridian design system defines `--radius-sm: 2px`, `--radius-md: 4px`, `--radius-lg: 6px`, `--radius-pill: 999px` with a max of 6px for non-pill elements. Found values of `8px`, `10px`, `11px`, `12px`, and `14px` in multiple files that violate the 6px maximum.
- Files: Worst offenders:
  - `static/css/components.css` line 9: `border-radius: 14px` on `.search-container`
  - `static/css/panels.css` lines 43, 119, 194: `border-radius: 12px`
  - `static/css/cards.css` line 10: `border-radius: 12px` on `.stat-card`
  - `static/css/overlays.css` lines 35, 49, 138: `border-radius: 14px`, `12px`
  - `static/css/responsive.css` lines 23, 38, 41: `border-radius: 10px`, `12px`
- Impact: Visual inconsistency. The design system's constraint of max 6px is not enforced.
- Fix approach: Replace all hardcoded border-radius with token references. Use `--radius-lg` (6px) as the maximum for rectangular elements. Only `--radius-pill` (999px) should exceed 6px. Audit responsive.css values separately since they may need different mobile radii.

### Hardcoded Spacing and Font Sizes [LOW]

- Issue: Spacing values (`padding`, `margin`, `gap`) and `font-size` values are hardcoded throughout CSS instead of using `--space-*` and `--text-*` tokens from the Meridian system. 12 hardcoded font-size declarations across 5 CSS files. Spacing values like `24px`, `14px`, `10px`, `18px` appear instead of `--space-6`, `--space-3`, `--space-2`, etc.
- Files: `static/css/layout.css`, `static/css/panels.css`, `static/css/cards.css`, `static/css/overlays.css`, `static/css/components.css`
- Impact: Spacing rhythm is inconsistent. Font sizes vary slightly between components that should match (e.g., `.74rem` vs `.76rem` vs `.78rem` in different panels).
- Fix approach: Lower priority than token and rgba migration. Address during the per-file migration pass.

## Frontend Quality

### render.js Complexity and Size [HIGH]

- Issue: `static/js/render.js` (930 lines) is the largest JS file and handles all DOM rendering via string concatenation with template literals. It builds complex HTML for breaches, stealers, social profiles, Discord cards, Xbox/Steam/Roblox cards, GHunt results, Minecraft history, victim file trees, and a file viewer overlay. Any rendering failure in `renderResults()` cascades -- if an intermediate panel throws, subsequent panels do not render.
- Files: `static/js/render.js` (930 lines)
- Impact: A single malformed API response can freeze the UI on "Scanning..." status with no error feedback to the user. The string concatenation approach makes XSS bugs hard to spot and audit.
- Fix approach: Add try/catch around each `render*()` call in `renderResults()` (lines 54-58) so one panel failure does not block others. Long-term: consider a lightweight templating approach or component system.

### Global Mutable State [MEDIUM]

- Issue: `static/js/state.js` declares all application state as global mutable variables: `mode`, `sfMode`, `selectedMods`, `activeCat`, `currentResult`, `history`, `quotaData`, `modulesRan`. Additional global state exists in `render.js`: `breachPage`, `pwdVisible`, `openVictimTrees`, `openTreeDirs`. And in `auth.js`: `authToken`, `authUser`.
- Files: `static/js/state.js` (all), `static/js/render.js` (lines 4-8), `static/js/auth.js` (lines 4-5)
- Impact: Any function can mutate any state. Race conditions are possible when multiple async operations complete simultaneously. State is not reset between searches (e.g., `openVictimTrees` persists across searches).
- Fix approach: For the current vanilla JS architecture, encapsulate state in a single object with getter/setter methods. Clear search-specific state before each new search.

### Inline onclick Handlers [MEDIUM]

- Issue: 11 inline `onclick` handlers in `static/js/render.js` template strings (lines 102, 122, 125, 369, 390, 670, 756, 760, 829, 847, plus more). These mix behavior with markup, make CSP `unsafe-inline` necessary, and complicate escaping.
- Files: `static/js/render.js` (11+ occurrences)
- Impact: CSP in `nginx.conf` line 65 requires `'unsafe-inline'` for scripts. Inline handlers are harder to audit for XSS than centralized event listeners.
- Fix approach: After rendering HTML, attach event listeners via `addEventListener()` using `data-*` attributes for parameters. This also enables removing `'unsafe-inline'` from the script-src CSP directive.

### No Error Boundaries [MEDIUM]

- Issue: If `renderResults()` or any of its child functions (`renderBreaches`, `renderStealers`, `renderSocial`, `renderHolehe`, `renderExtras`, `renderSpiderFoot`) throws an exception, the UI remains stuck on the scanning animation with no error feedback.
- Files: `static/js/render.js` (lines 11-63), `static/js/search.js`
- Impact: Users see an infinite spinner with no indication that results failed to render. They may retry the search, consuming API quota.
- Fix approach: Wrap `renderResults()` and each sub-renderer in try/catch blocks. On failure, display an error banner and log the error to console. Show partial results when possible.

## Infrastructure

### No CI/CD Pipeline [HIGH]

- Issue: No `.github/workflows/`, `.gitlab-ci.yml`, or any CI/CD configuration exists. Deployment is manual via `scp` to the VPS.
- Files: None (no CI/CD config files exist)
- Impact: No automated testing, linting, or security scanning before deployment. Local and VPS environments can drift. Rollback requires manual intervention.
- Fix approach: Add a GitHub Actions workflow with: (1) lint check, (2) future test execution, (3) Docker build verification, (4) optional auto-deploy via SSH on main branch push.

### No Tests Whatsoever [CRITICAL]

- Issue: Zero test files exist in the entire codebase. No `pytest`, `unittest`, `jest`, or any testing framework is configured. No test directory exists. The `requirements.txt` does not include any testing dependencies.
- Files: None (no test files exist anywhere)
- Impact: Every code change is a regression gamble. The backend has complex logic (JWT auth, rate limiting, SSE streaming, multi-source search orchestration) that is entirely untested. Security-critical code (password hashing, token validation, rate limiting) has no verification.
- Fix approach: Priority test targets:
  1. `api/main.py` auth flow: login, token creation/validation, role checks
  2. `modules/oathnet_client.py`: response parsing, error handling
  3. `api/main.py` rate limiting: verify fail-closed behavior
  4. `api/main.py` search input validation: verify sanitization
  Add `pytest`, `httpx` (for async test client), and `pytest-asyncio` to dev dependencies.

### Manual Deployment via scp [MEDIUM]

- Issue: Production deployment is done by copying files to the VPS via `scp`. There is no deployment script, no version tagging, and no rollback mechanism. The `docker-compose.yml` mounts local directories (`./api`, `./static`, `./modules`) as read-only volumes (lines 31-33), so changes are picked up on container restart, but there is no atomic deployment.
- Files: `docker-compose.yml` (lines 31-33)
- Impact: Partial file uploads can leave the application in an inconsistent state. No audit trail of what was deployed when. Rolling back requires manually re-uploading old files.
- Fix approach: Use git-based deployment (push to VPS, `git pull && docker compose up -d`). Alternatively, build Docker images with code baked in and tag with version numbers.

### SQLite as Production Database [LOW]

- Issue: SQLite is used for the audit log and rate limiting (`api/main.py` lines 58, 106-163, 291+). Under concurrent write load, SQLite's single-writer lock can cause `database is locked` errors. The `aiosqlite` connections are opened and closed per-operation (no connection pool).
- Files: `api/main.py` (lines 107-163 for rate limiting, 291+ for audit)
- Impact: For the current single-VPS, low-traffic use case, this is acceptable. Becomes a problem if traffic grows or if multiple worker processes are used. The rate limiter opens a new connection for every request.
- Fix approach: For current scale, add WAL mode (`PRAGMA journal_mode=WAL`) to the database initialization. For growth, migrate to PostgreSQL or use a single persistent aiosqlite connection with a lock.

## Dependencies at Risk

### python-jose is Unmaintained [MEDIUM]

- Issue: `python-jose[cryptography]==3.3.0` in `requirements.txt` (line 12) has not been updated since 2021 and has known security advisories. The PyPI page recommends migrating to `PyJWT` or `joserfc`.
- Files: `requirements.txt` (line 12), `api/main.py` (line 32: `from jose import JWTError, jwt`)
- Impact: Potential vulnerabilities in JWT handling. No future security patches expected.
- Fix approach: Replace with `PyJWT>=2.8.0`. Update imports from `jose` to `jwt`. The API is similar: `jwt.encode()` and `jwt.decode()` have compatible signatures.

### requests Library is Redundant [LOW]

- Issue: Both `requests==2.32.3` and `httpx==0.27.2` are in `requirements.txt`. `httpx` is imported in `api/main.py` but only `requests` is used by `oathnet_client.py`. Having two HTTP client libraries is redundant.
- Files: `requirements.txt` (lines 3, 8)
- Impact: Increased container image size and dependency surface area. Confusing for maintainers.
- Fix approach: When migrating `oathnet_client.py` to async, use `httpx.AsyncClient` and remove `requests` from `requirements.txt`. Also remove `aiohttp` (line 4) and `tenacity` (line 9) if unused.

## Test Coverage Gaps

### No Test Coverage At All [CRITICAL]

- What's not tested: Everything. Specifically:
  - JWT authentication and authorization flow
  - Password hashing and verification (`_safe_hash`, `_safe_verify`)
  - Rate limiting logic (fail-closed behavior)
  - Search query sanitization (`SearchRequest` validators)
  - OathNet API response parsing (breach, stealer, holehe)
  - SSE streaming protocol correctness
  - Admin user management CRUD
  - Input validation edge cases
- Files: `api/main.py` (all), `modules/oathnet_client.py` (all)
- Risk: Security-critical code paths (auth, rate limiting, input sanitization) could have regressions introduced silently. The password hashing uses a SHA256-then-bcrypt pattern that could break with library updates. The SSE streaming has complex error handling that could silently drop results.
- Priority: CRITICAL -- this is the single highest-impact improvement possible.

---

*Concerns analysis: 2026-03-25*
