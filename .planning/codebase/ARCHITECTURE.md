# Architecture

**Analysis Date:** 2026-03-25

## Pattern Overview

**Overall:** Monolithic backend + SPA frontend with SSE streaming

**Key Characteristics:**
- Single FastAPI file (`api/main.py`) handles auth, search orchestration, admin, and all API routes — no separation of concerns into sub-modules
- Frontend is a vanilla JS SPA served directly by FastAPI (`/` and `/admin` routes return HTML files)
- Search results are delivered via Server-Sent Events (SSE) — the client reads a streaming response and processes typed event objects as they arrive
- OSINT module calls are dispatched from within the single `_stream_search` async generator; modules are not independently invocable via the API
- SpiderFoot runs as a separate Docker sidecar; all other OSINT modules run in-process or call OathNet REST API

## Layers

**Nginx Reverse Proxy:**
- Purpose: TLS termination, rate limiting, SSE buffering control
- Location: `nginx.conf`
- Contains: Two rate limit zones (`api: 30r/m`, `search: 5r/m`), SSL config, proxy rules
- Depends on: Let's Encrypt certs via Certbot sidecar
- Used by: All inbound traffic on ports 80/443

**FastAPI Application (`api/main.py`):**
- Purpose: Authentication, request routing, search orchestration, admin API
- Location: `api/main.py` (single file, ~1263 lines)
- Contains:
  - Pydantic request models (`LoginRequest`, `SearchRequest`)
  - JWT auth functions (`_create_token`, `_decode_token`, `get_current_user`, `get_admin_user`)
  - SQLite audit log helpers (`_init_audit_db`, `_log_search`)
  - SQLite-backed rate limiter (`_check_rate`, `_init_rate_table`)
  - Query type detection (`detect_type`)
  - SSE search generator (`_stream_search` with per-module `with_timeout` wrappers)
  - SpiderFoot poller (`_run_spiderfoot`)
  - All HTTP route handlers
- Depends on: `modules/` package, SQLite, OathNet API
- Used by: Nginx, browser clients

**OSINT Modules (`modules/`):**
- Purpose: Thin wrappers around external OSINT services
- Location: `modules/oathnet_client.py`, `modules/sherlock_wrapper.py`, `modules/report_generator.py`, `modules/spiderfoot_wrapper.py`
- Contains: Synchronous HTTP clients; dataclass result models; called via `asyncio.to_thread()` from main
- Depends on: OathNet REST API (`https://oathnet.org/api`), direct platform HTTP checks (Sherlock)
- Used by: `api/main.py` exclusively (imported inline inside route functions and `_stream_search`)

**Frontend SPA (`static/`):**
- Purpose: Full browser UI — auth, search, results rendering, export, cases management
- Location: `static/index.html`, `static/js/*.js`, `static/css/*.css`
- Contains: 9 JS modules loaded as plain script tags in dependency order; 9 CSS files
- Depends on: JWT stored in `localStorage`; fetches `/api/*` endpoints with `Authorization: Bearer` header
- Used by: End users via browser

**Data Layer (`/app/data/`):**
- Purpose: Persistent state across container restarts
- Location: Docker volume `nexus_data` mounted at `/app/data` inside container
- Contains:
  - `audit.db` — SQLite database with tables: `searches`, `rate_limits`, `quota_log`
  - `users.json` — multi-user store (bcrypt-hashed passwords, roles, active flag)
- Depends on: `aiosqlite` for async access
- Used by: `api/main.py`

## Data Flow

**Authentication Flow:**

1. Browser loads `static/index.html`; `init()` calls `checkAuth()` in `auth.js`
2. `checkAuth()` calls `GET /api/me` with stored JWT — if valid, renders nav user badge
3. On failure, shows auth screen; user submits credentials to `POST /api/login`
4. Backend verifies via `_verify_user()` (bcrypt check against `users.json`), returns JWT
5. Frontend stores token in `localStorage['nx_token']`; all subsequent calls use `Authorization: Bearer` header
6. `apiFetch()` in `auth.js` intercepts 401 responses and forces re-login

**Search Flow (SSE):**

1. `startSearch()` in `search.js` POSTs `{ query, mode, modules, spiderfoot_mode }` to `/api/search`
2. FastAPI validates JWT via `get_current_user` dependency, checks rate limit via `_check_rate`
3. `_stream_search` generator begins: detects query type (`detect_type`), resolves which modules to run
4. Modules execute sequentially (with some parallelism for breach+stealer); each `yield event(...)` pushes an SSE frame
5. `OathnetClient` methods run in thread pool via `asyncio.to_thread()`; wrapped in `with_timeout()` per module
6. Client-side `handleEvent(evt)` dispatches on `evt.type` to populate `currentResult` object
7. On `type: "done"`, frontend calls `renderResults()` and `saveHistory()`
8. Audit log written as a fire-and-forget `asyncio.create_task(_log_search(...))`

**SSE Event Types (backend → frontend):**
- `start` — announces query type and planned modules
- `progress` — label + percent complete
- `oathnet` — breach/stealer/holehe data + quota info
- `sherlock` — social platform results
- `discord` / `ip_info` / `subdomains` / `steam` / `xbox` / `roblox` / `ghunt` / `minecraft` / `victims` / `discord_roblox` — per-module payloads
- `spiderfoot_started` / `spiderfoot_progress` / `spiderfoot` — SpiderFoot lifecycle
- `module_error` — module-level failure (non-fatal)
- `done` — elapsed time, timestamp, modules_run list

**State Management:**
- Global JS variables in `state.js`: `currentResult`, `history`, `cases`, `mode`, `sfMode`, `selectedMods`, `modulesRan`, `quotaData`
- History (last 20 searches) and saved cases (max 50) persisted to `localStorage`
- Backend state: `users.json` (users) + `audit.db` (audit, rate limits, quota log) on Docker volume

## Key Abstractions

**`OathnetClient` (`modules/oathnet_client.py`):**
- Purpose: Typed wrapper around the OathNet REST API (`https://oathnet.org/api`)
- Methods: `search_breach`, `search_stealer_v2`, `holehe`, `ip_info`, `discord_userinfo`, `discord_username_history`, `discord_to_roblox`, `steam_lookup`, `xbox_lookup`, `roblox_lookup`, `ghunt`, `minecraft_history`, `victims_search`, `victims_manifest`, `victims_file`, `extract_subdomains`
- Returns: `OathnetResult` dataclass (contains `BreachRecord[]`, `StealerRecord[]`, `OathnetMeta`)
- Auth: `x-api-key` header (not Bearer)

**`OathnetResult` / `BreachRecord` / `StealerRecord` / `OathnetMeta` (dataclasses in `modules/oathnet_client.py`):**
- Purpose: Typed result containers passed from modules to `_stream_search`, then serialized to SSE JSON
- Pattern: Dataclass with `field(default_factory=...)` for all collection fields

**`SearchRequest` (Pydantic model in `api/main.py`):**
- Purpose: Validated inbound search payload
- Validators: `sanitize_query` (strips control chars, SQL injection chars), `validate_mode`, `validate_sf_mode`

**`currentResult` (JS object in `state.js` / `search.js`):**
- Purpose: In-memory accumulator for all SSE events from a single search
- Shape: `{ query, oathnet, sherlock, extras: { discord[], ip, subdomains, spiderfoot, steam, xbox, roblox, ghunt, minecraft, victims, discord_roblox }, elapsed, timestamp }`

**`with_timeout(coro, module, default)` (`api/main.py` line 465):**
- Purpose: Per-module async timeout wrapper that logs and returns default on timeout (does not abort entire search)
- Returns: `(result, timed_out: bool)`
- Timeouts: defined in `MODULE_TIMEOUTS` dict (10–60s per module)

## Entry Points

**`GET /` and `HEAD /`:**
- Location: `api/main.py` line 376
- Triggers: Browser navigation
- Responsibilities: Serves `static/index.html` directly as HTML response

**`GET /admin`:**
- Location: `api/main.py` line 385
- Triggers: Nav admin link (visible only to `role=admin` users)
- Responsibilities: Serves `static/admin.html`

**`POST /api/login`:**
- Location: `api/main.py` line 405
- Triggers: Auth form submission
- Responsibilities: Rate-limits login attempts (5/min/IP), verifies credentials, returns JWT

**`POST /api/search`:**
- Location: `api/main.py` line 494
- Triggers: `startSearch()` in `search.js`
- Responsibilities: JWT auth, rate limit (20/min/IP), returns `StreamingResponse` wrapping `_stream_search` generator

**`GET /health`:**
- Location: `api/main.py` line 1259
- Triggers: Docker healthcheck (`curl -f http://localhost:8000/health`)
- Responsibilities: Returns `{ status: "ok", version: "3.0.0", timestamp }`

**`init()` (frontend):**
- Location: `static/js/state.js` line 35; invoked at bottom of `static/index.html`
- Triggers: DOMContentLoaded
- Responsibilities: `checkAuth()`, builds category/module chips, checks SpiderFoot status, renders history, initializes keyboard shortcuts

## Error Handling

**Strategy:** Module-level isolation — individual module failures emit `{ type: "module_error" }` SSE events and do not abort the search stream. The `done` event is always emitted.

**Patterns:**
- Module timeout: `with_timeout()` returns `(default, True)`; calling code yields `module_error` event
- Module exception: bare `except Exception as exc` blocks in `_stream_search` yield `module_error` events
- Auth failure: FastAPI `HTTPException(401)` with `WWW-Authenticate: Bearer` header; frontend `apiFetch()` intercepts 401 and forces re-login
- Rate limit: `HTTPException(429)` returned before stream opens
- DB unavailable: rate limiter fails closed (returns `False`, blocks request)

## Cross-Cutting Concerns

**Logging:** Python `logging` module, level from `LOG_LEVEL` env var (default `WARNING`); logger named `"nexusosint"`

**Validation:**
- Backend: Pydantic `SearchRequest` validators strip control chars and SQL injection patterns; `_validate_id()` used on `log_id`/`file_id` path params
- Frontend: `detectType()` in `utils.js` mirrors backend `detect_type()` for real-time badge display

**Authentication:** All API routes except `/api/auth`, `/api/login`, `/health` require `Depends(get_current_user)`; admin routes additionally require `Depends(get_admin_user)` (checks `role == "admin"`)

**Rate Limiting:** Two-layer — Nginx (`30r/m` general API, `5r/m` search) + SQLite-backed in-process limiter (`20 searches/min/IP`, `5 logins/min/IP`)

**Security Headers:** `SecurityHeadersMiddleware` adds `X-Robots-Tag`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Embedder-Policy` to all responses; Nginx adds HSTS, X-Frame-Options, CSP, etc.

---

*Architecture analysis: 2026-03-25*
