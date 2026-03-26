<!-- GSD:project-start source:PROJECT.md -->
## Project

**NexusOSINT**

A premium OSINT (Open Source Intelligence) SaaS platform for security professionals, investigators, and intelligence analysts. Aggregates breach data, stealer logs, social media profiles, and infrastructure intel through a unified search interface with SSE streaming results. Production at nexusosint.uk v3.0.0.

**Core Value:** A single search query returns comprehensive intelligence from 13+ OSINT modules with professional-grade data presentation — density without chaos.

### Constraints

- **Stack lock**: FastAPI + vanilla HTML/CSS/JS + SQLite + Docker — no framework changes this milestone
- **Zero visual regression**: Phase 2 token migration must produce identical visual output
- **Amber/noir identity**: Color palette is brand identity — never change accent to green/blue/other
- **File protection**: Do NOT modify docker-compose.yml, nginx.conf, Dockerfile, entrypoint.sh, admin.html, modules/*.py
- **Known traps**: Never use passlib, slowapi, su-exec, `from __future__ import annotations`, `user: "1000:1000"` in compose, `internal: true` on Docker network
- **Sync risk**: Local files may differ from VPS — verify before deploying
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11 — Backend API, all modules (`api/main.py`, `modules/`)
- JavaScript (ES2020+, no framework) — Frontend SPA (`static/js/`)
- HTML/CSS — Frontend markup and styling (`static/index.html`, `static/css/`)
## Runtime
- Python 3.11 (slim Docker image: `python:3.11-slim`)
- Browser (vanilla JS, no build step required)
- pip (no version pinned)
- Lockfile: absent — `requirements.txt` with pinned versions only
## Frameworks
- FastAPI 0.115.0 — HTTP API server, SSE streaming, static file serving
- Uvicorn 0.30.6 (with `[standard]` extras) — ASGI server, launched via `entrypoint.sh`
- Pydantic 2.8.2 — Request/response validation, field validators
- Starlette (transitive via FastAPI) — Middleware base
- None detected — no test framework configured, no test files present
- No build step — frontend is raw HTML/CSS/JS, served as static files
- Docker + docker-compose for containerised deployment
- Nginx (Alpine image) as reverse proxy with SSL termination
## Key Dependencies
- `python-jose[cryptography]==3.3.0` — JWT token creation and verification (HS256)
- `bcrypt==4.2.1` — Password hashing (used directly, bypassing passlib)
- `aiosqlite==0.20.0` — Async SQLite for audit log, rate limiter, quota tracking
- `httpx==0.27.2` — Async HTTP client used in SpiderFoot polling loop
- `aiohttp==3.10.5` — Async HTTP used in `sherlock_wrapper.py` platform checks
- `requests==2.32.3` — Sync HTTP used in `oathnet_client.py` (wrapped via `asyncio.to_thread`)
- `python-dotenv==1.0.1` — Loads `.env` into environment at startup
- `aiofiles==24.1.0` — Async file I/O
- `tenacity==8.5.0` — Retry logic (imported in requirements, not yet wired to OathNet calls)
## Configuration
- All config loaded from `.env` via `python-dotenv` in `api/main.py`
- Required vars: `OATHNET_API_KEY`, `JWT_SECRET`
- Optional vars: `APP_PASSWORD` (legacy single-user), `ALLOWED_ORIGINS`, `LOG_LEVEL`, `JWT_EXPIRE_HOURS`, `SPIDERFOOT_URL`, `SPIDERFOOT_PATH`, `SPIDERFOOT_TIMEOUT`
- If `JWT_SECRET` is absent, an ephemeral secret is derived at startup — tokens invalidated on restart
- `Dockerfile` — Python 3.11-slim base, non-root `appuser` (uid 1000), exposes port 8000
- `docker-compose.yml` — Defines `nexus` (app), `nginx` (proxy), `certbot` (SSL renewal) services
- `nginx.conf` — HTTP→HTTPS redirect, TLS 1.2/1.3, rate zones: `api` 30r/m, `search` 5r/m
- `entrypoint.sh` — Drops to `appuser` via `gosu`, launches `uvicorn api.main:app --proxy-headers`
## Platform Requirements
- Docker + docker-compose (standard deployment path)
- Python 3.11+ if running locally without Docker
- `.env` file with `OATHNET_API_KEY` and `JWT_SECRET`
- Docker host with ports 80/443 exposed
- Let's Encrypt certificates managed by `certbot` container
- Domain: `nexusosint.uk` (hardcoded in `nginx.conf`)
- Persistent Docker volume `nexus_data` at `/app/data` — stores `users.json`, `audit.db`
- Optional: SpiderFoot instance reachable at `SPIDERFOOT_URL` (default `http://spiderfoot:5001`) — not included in `docker-compose.yml`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Module files use `snake_case`: `oathnet_client.py`, `sherlock_wrapper.py`, `report_generator.py`, `spiderfoot_wrapper.py`
- Private helpers prefix with `_`: `_load_users`, `_save_users`, `_safe_hash`, `_safe_verify`, `_init_audit_db`, `_log_search`, `_stream_search`, `_serialize_breaches`
- Constants and config in `UPPER_SNAKE_CASE`: `OATHNET_BASE_URL`, `JWT_SECRET`, `MODULE_TIMEOUTS`, `DATA_DIR`, `AUDIT_DB`
- Dataclasses use `PascalCase`: `BreachRecord`, `StealerRecord`, `OathnetResult`, `OathnetMeta`, `SherlockResult`, `PlatformResult`
- Pydantic models use `PascalCase`: `LoginRequest`, `SearchRequest`
- Files use `camelCase.js`: `auth.js`, `cases.js`, `export.js`, `history.js`, `panels.js`, `render.js`, `search.js`, `state.js`, `utils.js`
- Functions use `camelCase`: `startSearch`, `handleEvent`, `renderResults`, `buildCatChips`, `toggleMod`, `showToast`, `detectType`
- Module-level state variables use `camelCase`: `authToken`, `authUser`, `currentResult`, `selectedMods`, `activeCat`
- Constants use `UPPER_SNAKE_CASE`: `CATEGORIES`, `MOD_LABELS`, `TYPE_LABELS`, `BREACH_PAGE_SIZE`
- localStorage keys use `nx_` prefix: `nx_token`, `nx_user`, `nx_history`, `nx_cases`
- BEM-flavored kebab-case: `.discord-card`, `.discord-card-inner`, `.discord-avatar`, `.search-container`, `.search-input`, `.nav-logo-mark`
- State modifiers are bare class additions: `.active`, `.visible`, `.done`, `.error`, `.online`, `.copied`, `.saved`
- Panel/section IDs use `camelCase`: `casesPanel`, `scanModules`, `sfOptions`, `modChips`, `catChips`
## Code Style
- No formatter config found (no `pyproject.toml`, `.flake8`, `setup.cfg`). Style is manually consistent.
- 4-space indentation throughout
- Trailing inline alignment for constants and short multi-assignments using spaces:
- Max line length approximately 100–120 characters in practice (not enforced)
- Section headers use `# ── Section Name ──────────...` style banners consistently
- 2-space indentation throughout
- Single quotes for strings: `'nx_token'`, `'auto'`, `'passive'`
- Template literals for HTML generation
- Arrow functions for simple callbacks: `e => { ... }`, `c => c.classList.remove('active')`
- Section headers use `// ══════════════...` banners at file level and `// ── subsection ──` inline
- 2-space indentation
- Section banners: `/* ══════════... */` at top of each file
- Values use `var(--token)` for all design tokens from `tokens.css`
- Inline values only for one-off colors not in the token system
## Import Organization
## Error Handling
- Route handlers use `HTTPException` with explicit `status_code` and `detail` string:
- Module-level helper functions swallow exceptions and return safe defaults with a `logger.warning` or `logger.error` call:
- SSE stream handlers catch per-module exceptions and yield `module_error` events rather than crashing the stream:
- Rate limiter uses fail-closed on DB errors: `return False  # fail closed — prevent abuse if DB unavailable`
- External API calls in `OathnetClient` use `(bool, dict)` return tuples — never raise:
- Per-module timeouts via `with_timeout()` wrapper — returns `(default, timed_out: bool)` rather than raising:
- `apiFetch()` centralizes 401 handling: clears token, forces re-login, throws
- All `fetch` calls are wrapped in `try/catch`; errors shown via `showToast()`
- Empty `catch(e) {}` is used for non-critical flows (e.g., `checkAuth` probe requests)
- SSE event parsing uses silent `try/catch` per line: `try { evt = JSON.parse(...) } catch(e) {}`
## Logging
- Use `%s` format args, never f-strings in logger calls: `logger.warning("Quota save failed: %s", exc)`
- `logger.info` for startup events
- `logger.warning` for recoverable failures (timeouts, DB errors, API errors)
- `logger.error` for unexpected exceptions in business logic
- JavaScript has no structured logging — user-visible errors go to `showToast()`; debug info is silent
## Comments
- Module docstrings at file top with version info and key design decisions (all modules use this)
- Inline comments for non-obvious logic: `# fail closed — prevent abuse if DB unavailable`
- Section banners `# ── Section Name ───...` replace large block comments — used consistently throughout `main.py`
- Function docstrings on public/dependency functions: `"""Dependency: validates JWT and returns user payload."""`
- Portuguese comments appear in `spiderfoot_wrapper.py` and `report_generator.py` (localization inconsistency)
- Section banners `// ══════════ SECTION NAME ══════════` at file top
- Subsection banners `// ── subsection ──` inline
- Inline comments for non-obvious logic: `// Token expired — force re-login`
- No JSDoc usage anywhere
- Section banners `/* ══════════ SECTION ══════════ */`
- Inline comments for version notes: `/* Nav: refined glassmorphism (enhanced v3.1) */`
## Function Design
- Private helpers prefixed with `_`, kept small and single-purpose
- Async functions used for all I/O; sync functions for pure computation
- Dataclass-based return types preferred over raw dicts in modules (`OathnetResult`, `SherlockResult`)
- Route handlers are thin — delegate to private generator/helper functions
- `_stream_search` is the largest function (~400 lines) — a known complexity issue
- Functions are imperative and DOM-manipulating, typically 5–30 lines
- Global state (`currentResult`, `history`, `cases`, `selectedMods`) is mutated directly
- Event handler functions follow `verbNoun` naming: `startSearch`, `saveCase`, `deleteCase`, `toggleMod`, `loadCase`
- HTML generation uses template literal strings, not DOM API: `` ` <div class="${cls}">${content}</div>` ``
## Module Design
- Each module in `modules/` is a self-contained class or function set with its own dataclasses
- No barrel `__init__.py` re-exports — imports are direct: `from modules.oathnet_client import OathnetClient`
- `api/main.py` imports modules inline inside `_stream_search` to avoid circular import issues
- No module system — global namespace only
- Each `.js` file groups related functions under a section banner
- Cross-file calls are direct function calls (e.g., `render.js` calls `riskLabel()` from `utils.js`)
- Shared state lives in `state.js` (global `let` vars) and `auth.js` (`authToken`, `authUser`)
## CSS Design Tokens
- Semantic tokens: `--color-bg-base`, `--color-accent`, `--color-critical`, `--color-text-primary`
- Legacy aliases retained for backward compat: `--bg`, `--amber`, `--red`, `--text`, `--mono`
- Always prefer semantic token names in new code; legacy aliases still used in existing CSS
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Single FastAPI file (`api/main.py`) handles auth, search orchestration, admin, and all API routes — no separation of concerns into sub-modules
- Frontend is a vanilla JS SPA served directly by FastAPI (`/` and `/admin` routes return HTML files)
- Search results are delivered via Server-Sent Events (SSE) — the client reads a streaming response and processes typed event objects as they arrive
- OSINT module calls are dispatched from within the single `_stream_search` async generator; modules are not independently invocable via the API
- SpiderFoot runs as a separate Docker sidecar; all other OSINT modules run in-process or call OathNet REST API
## Layers
- Purpose: TLS termination, rate limiting, SSE buffering control
- Location: `nginx.conf`
- Contains: Two rate limit zones (`api: 30r/m`, `search: 5r/m`), SSL config, proxy rules
- Depends on: Let's Encrypt certs via Certbot sidecar
- Used by: All inbound traffic on ports 80/443
- Purpose: Authentication, request routing, search orchestration, admin API
- Location: `api/main.py` (single file, ~1263 lines)
- Contains:
- Depends on: `modules/` package, SQLite, OathNet API
- Used by: Nginx, browser clients
- Purpose: Thin wrappers around external OSINT services
- Location: `modules/oathnet_client.py`, `modules/sherlock_wrapper.py`, `modules/report_generator.py`, `modules/spiderfoot_wrapper.py`
- Contains: Synchronous HTTP clients; dataclass result models; called via `asyncio.to_thread()` from main
- Depends on: OathNet REST API (`https://oathnet.org/api`), direct platform HTTP checks (Sherlock)
- Used by: `api/main.py` exclusively (imported inline inside route functions and `_stream_search`)
- Purpose: Full browser UI — auth, search, results rendering, export, cases management
- Location: `static/index.html`, `static/js/*.js`, `static/css/*.css`
- Contains: 9 JS modules loaded as plain script tags in dependency order; 9 CSS files
- Depends on: JWT stored in `localStorage`; fetches `/api/*` endpoints with `Authorization: Bearer` header
- Used by: End users via browser
- Purpose: Persistent state across container restarts
- Location: Docker volume `nexus_data` mounted at `/app/data` inside container
- Contains:
- Depends on: `aiosqlite` for async access
- Used by: `api/main.py`
## Data Flow
- `start` — announces query type and planned modules
- `progress` — label + percent complete
- `oathnet` — breach/stealer/holehe data + quota info
- `sherlock` — social platform results
- `discord` / `ip_info` / `subdomains` / `steam` / `xbox` / `roblox` / `ghunt` / `minecraft` / `victims` / `discord_roblox` — per-module payloads
- `spiderfoot_started` / `spiderfoot_progress` / `spiderfoot` — SpiderFoot lifecycle
- `module_error` — module-level failure (non-fatal)
- `done` — elapsed time, timestamp, modules_run list
- Global JS variables in `state.js`: `currentResult`, `history`, `cases`, `mode`, `sfMode`, `selectedMods`, `modulesRan`, `quotaData`
- History (last 20 searches) and saved cases (max 50) persisted to `localStorage`
- Backend state: `users.json` (users) + `audit.db` (audit, rate limits, quota log) on Docker volume
## Key Abstractions
- Purpose: Typed wrapper around the OathNet REST API (`https://oathnet.org/api`)
- Methods: `search_breach`, `search_stealer_v2`, `holehe`, `ip_info`, `discord_userinfo`, `discord_username_history`, `discord_to_roblox`, `steam_lookup`, `xbox_lookup`, `roblox_lookup`, `ghunt`, `minecraft_history`, `victims_search`, `victims_manifest`, `victims_file`, `extract_subdomains`
- Returns: `OathnetResult` dataclass (contains `BreachRecord[]`, `StealerRecord[]`, `OathnetMeta`)
- Auth: `x-api-key` header (not Bearer)
- Purpose: Typed result containers passed from modules to `_stream_search`, then serialized to SSE JSON
- Pattern: Dataclass with `field(default_factory=...)` for all collection fields
- Purpose: Validated inbound search payload
- Validators: `sanitize_query` (strips control chars, SQL injection chars), `validate_mode`, `validate_sf_mode`
- Purpose: In-memory accumulator for all SSE events from a single search
- Shape: `{ query, oathnet, sherlock, extras: { discord[], ip, subdomains, spiderfoot, steam, xbox, roblox, ghunt, minecraft, victims, discord_roblox }, elapsed, timestamp }`
- Purpose: Per-module async timeout wrapper that logs and returns default on timeout (does not abort entire search)
- Returns: `(result, timed_out: bool)`
- Timeouts: defined in `MODULE_TIMEOUTS` dict (10–60s per module)
## Entry Points
- Location: `api/main.py` line 376
- Triggers: Browser navigation
- Responsibilities: Serves `static/index.html` directly as HTML response
- Location: `api/main.py` line 385
- Triggers: Nav admin link (visible only to `role=admin` users)
- Responsibilities: Serves `static/admin.html`
- Location: `api/main.py` line 405
- Triggers: Auth form submission
- Responsibilities: Rate-limits login attempts (5/min/IP), verifies credentials, returns JWT
- Location: `api/main.py` line 494
- Triggers: `startSearch()` in `search.js`
- Responsibilities: JWT auth, rate limit (20/min/IP), returns `StreamingResponse` wrapping `_stream_search` generator
- Location: `api/main.py` line 1259
- Triggers: Docker healthcheck (`curl -f http://localhost:8000/health`)
- Responsibilities: Returns `{ status: "ok", version: "3.0.0", timestamp }`
- Location: `static/js/state.js` line 35; invoked at bottom of `static/index.html`
- Triggers: DOMContentLoaded
- Responsibilities: `checkAuth()`, builds category/module chips, checks SpiderFoot status, renders history, initializes keyboard shortcuts
## Error Handling
- Module timeout: `with_timeout()` returns `(default, True)`; calling code yields `module_error` event
- Module exception: bare `except Exception as exc` blocks in `_stream_search` yield `module_error` events
- Auth failure: FastAPI `HTTPException(401)` with `WWW-Authenticate: Bearer` header; frontend `apiFetch()` intercepts 401 and forces re-login
- Rate limit: `HTTPException(429)` returned before stream opens
- DB unavailable: rate limiter fails closed (returns `False`, blocks request)
## Cross-Cutting Concerns
- Backend: Pydantic `SearchRequest` validators strip control chars and SQL injection patterns; `_validate_id()` used on `log_id`/`file_id` path params
- Frontend: `detectType()` in `utils.js` mirrors backend `detect_type()` for real-time badge display
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
