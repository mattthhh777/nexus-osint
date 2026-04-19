# Architecture

**Analysis Date:** 2026-04-19

## Pattern Overview

**Overall:** Monolithic FastAPI application with layered concerns but co-located in single file.

**Key Characteristics:**
- Single entry point in `api/main.py` (1770 lines) handling routing, authentication, business logic, and database access
- Streaming SSE responses for long-running OSINT scans via `_stream_search()`
- Async-first with asyncio TaskGroup + Semaphore for concurrent module execution
- SQLite backend with WAL mode + serialized writes via asyncio.Queue (`api/db.py`)
- Frontend is pure Vanilla JavaScript — zero backend logic executed on client
- External service integrations (OathNet, SpiderFoot, Sherlock) abstracted into `modules/`

## Layers

**Route Layer:**
- Location: `api/main.py` lines 557-1755 (endpoint definitions)
- Contains: All `@app.get()` and `@app.post()` handlers
- Examples:
  - `/api/search` (main SSE streaming endpoint) — line 783
  - `/api/admin/stats` — line 1320
  - `/api/admin/logs` — line 1371
  - `/api/auth/login` — line 650
  - `/api/auth/logout` — line 692
  - `/health` — line 1684
  - `/sf/status` (SpiderFoot status) — line 1672
  - `/api/victims/*` (breach database endpoints) — lines 1599-1672
- Depends on: `Depends(get_current_user)`, `Depends(get_admin_user)`, rate limiting
- Used by: FastAPI app (request → handler → response)

**Business Logic / Orchestration Layer:**
- Location: `api/main.py` lines 804-1314 (`_stream_search()` function)
- Contains: OSINT scan orchestration, module execution decisions, result aggregation
- Key logic:
  - Determines query type (`detect_type()` line 706)
  - Decides which modules to run based on `req.mode` (automated vs manual)
  - Submits modules to orchestrator
  - Aggregates SSE events streamed to client
  - Logs search to database
  - Handles caching of breach/stealer results
- Depends on: `oathnet_client`, `TaskOrchestrator`, database, module wrappers
- Used by: Route handler `/api/search`

**Module Integration Layer:**
- Location: `modules/` directory
- Contains:
  - `oathnet_client.py` — async HTTP wrapper for OathNet API (breach, stealer, holehe, discord lookups)
  - `sherlock_wrapper.py` — social platform username search
  - `spiderfoot_wrapper.py` — domain/IP reconnaissance
  - `report_generator.py` — not actively used in main flow, legacy
- Each module is called within `_stream_search()` or via endpoints
- Design: Each module returns dataclass result or raises exception caught in `_stream_search()`

**Authentication & Authorization Layer:**
- Location: `api/main.py` lines 151-505
- Contains:
  - JWT generation (`_create_token()` line 398)
  - JWT validation (`_decode_token()` line 409)
  - User lookup (`_verify_user()` line 379)
  - Token blacklist checking (`_check_blacklist()` line 425)
  - Token revocation (`_revoke_token()` line 464)
  - User file management (`_load_users()` line 326, `_save_users()` line 343)
  - Password hashing (`_safe_hash()` line 350, `_safe_verify()` line 356)
  - Dependency functions: `get_current_user()` line 473, `get_admin_user()` line 497
- Uses: `bcrypt` for password, `python-jose` for JWT
- All validation is **backend-only** — frontend receives no permission data

**Database Layer:**
- Location: `api/db.py` (327 lines)
- Contains: DatabaseManager class managing SQLite connection lifecycle
- Implements:
  - Single persistent aiosqlite connection (no pooling)
  - WAL mode for concurrent read/write safety
  - Background writer task consuming asyncio.Queue for serialized writes
  - Methods: `write()`, `write_await()`, `read()`, `read_one()`, `read_stream()`
  - Schema: `searches` (audit log), `token_blacklist`, `rate_limits`, `quota_log` tables
- Depends on: aiosqlite
- Used by: All database operations throughout codebase
- Instance: Module-level singleton `db` at bottom of file

**Concurrency Control Layer:**
- Location: `api/orchestrator.py` (233 lines) + `api/watchdog.py` (150 lines)
- Contains:
  - `TaskOrchestrator` — manages concurrent OSINT module execution
  - Global Semaphore(5) ceiling on concurrent tasks
  - OathNet-scoped Semaphore(3) to prevent starvation of faster modules
  - asyncio.Queue bridge for incremental result delivery
  - Phase 10: singleton `get_orchestrator()` for health check access
  - Memory watchdog that monitors psutil and adjusts ceiling under pressure
  - DegradationMode enum: NORMAL (ceiling=5) / REDUCED (ceiling=2) / CRITICAL (ceiling=0)
- Used by: `_stream_search()` to submit concurrent modules, health endpoint to report status

**Utility & Helper Layer:**
- Location: Scattered throughout `api/main.py`
- Functions:
  - `detect_type()` (line 706) — classify query as email/IP/username/etc
  - `with_timeout()` (line 736) — wrap coroutine with timeout + fallback
  - `_serialize_breaches()` (line 764) — transform breach objects to JSON
  - `_serialize_stealers()` (line 773) — transform stealer objects to JSON
  - `_parse_discord_history()` (line 1542) — parse raw Discord history JSON
  - `_validate_id()` (line 1624) — validate victim ID format
  - Caching: `_get_cached()`, `_set_cached()` (lines 138-147) using TTLCache
  - Rate limiting: `_rate_key()` (line 270), `_rate_limit_handler()` (line 288)

**Middleware & Cross-Cutting Concerns:**
- Location: `api/main.py` lines 225-540
- SecurityHeadersMiddleware (line 537) — injects CSP, X-Frame-Options, etc
- CORS middleware — allows same-origin or configured cross-origin
- Rate limiting via slowapi — per endpoint, per IP, per user
- Error handling in lifespan — validates JWT secret, starts watchdog, initializes DB

## Data Flow

**Search Flow (Most Complex):**

1. Client submits `/api/search` with query + modules (lines 783-802)
   - Request validated: `SearchRequest` Pydantic model (line 155)
   - Rate limit checked: `@limiter.limit(RL_SEARCH_LIMIT)`
   - Auth checked: `Depends(get_current_user)` extracts JWT from header
   - Degradation mode checked: if CRITICAL, return 503 (line 789)

2. Handler calls `StreamingResponse(_stream_search(...), media_type="text/event-stream")`
   - Returns immediately; streaming starts in background

3. Inside `_stream_search()` (lines 804-1314):
   - Registers sentinel task in orchestrator for active count tracking
   - Detects query type (email/IP/username/etc)
   - Decides which modules to run based on query type + req.mode
   - Yields SSE event: `{"type": "start", ...}`

4. Module Execution (parallel via TaskOrchestrator):
   - **Breach + Stealer** (lines 902-997): OathNet API call, cache check, serialization
   - **Sherlock** (lines 1023-1047): Social platform search
   - **Discord** (lines 1049-1191): Discord user lookup + history
   - **IP Info** (lines 1193-1210): GeoIP lookup
   - **Subdomain** (lines 1212-1247): DNS enumeration
   - **Steam/Xbox/Roblox** (lines 1249-1299): Game platform lookups
   - Each module wrapped in `try/except` to yield module_error on failure
   - Results streamed as SSE events incrementally

5. Logging (line 1305):
   - `_log_search()` writes audit record to `searches` table
   - Includes: username, IP, query, modules run, result counts, elapsed time

6. Response Completion:
   - Yields final `{"type": "done", ...}` event
   - Sentinel released; orchestrator deregisters search
   - Client-side SSE handler accumulates events into result state

**Authentication Flow:**

1. Client POSTs `/api/auth/login` with username + password (line 650)
2. Handler calls `_verify_user()` (line 379) → checks users.json file
3. On success: calls `_create_token()` (line 398) → returns JWT with expiry
4. Client stores JWT in memory (never localStorage per F7)
5. Subsequent requests include JWT in `Authorization: Bearer <token>` header
6. Middleware/endpoint `get_current_user()` (line 473) → `_decode_token()` + `_check_blacklist()`
7. On logout: `_revoke_token()` (line 464) → adds JTI to `token_blacklist` table

**Database Write Path:**

1. Code calls `db.write(sql, params)` or `db.write_await(sql, params)`
2. Write queued to `_write_queue` (asyncio.Queue)
3. Background writer task (`_writer_loop()` in db.py) dequeues and executes
4. **All writes are serialized** — no concurrent writes even if multiple coroutines try
5. Reads bypass queue — direct connection access (WAL mode allows safe concurrent reads)

## State Management

**Search State (Client):**
- Managed in `static/js/state.js` and `static/js/render.js`
- Global `g_state` object accumulates SSE events
- State structure: `{ results: {}, panels: {}, stats: {}, ...}`
- No server-side session — state rebuilt from SSE stream

**User Session (Server):**
- JWT stored in HTTP-only cookie (set in login response)
- Token contains username + role + expiry + JTI (unique identifier)
- No server-side session table — JTI used only for blacklist on logout
- User file (`users.json`) is single source of truth for credentials

**Quota Tracking:**
- OathNet returns `meta.used_today`, `meta.left_today`, `meta.daily_limit`
- Saved to `quota_log` table via `_save_quota()` (line 191)
- Used by admin dashboard (`/api/admin/stats` returns latest quota)

**Caching (In-Memory):**
- Module: TTLCache with 5-minute TTL
- Cached: breach results, stealer results, holehe domains
- Key: `{endpoint}:{query}` (line 133)
- Bypass: Checked before each API call; if miss, API called then cached

## Key Abstractions

**TaskOrchestrator:**
- Purpose: Manage concurrent OSINT module execution without OOM
- Pattern: Dual semaphore (global + OathNet scoped)
- Location: `api/orchestrator.py`
- Usage: `orchestrator.submit(name, coro, is_oathnet=bool)` then `async for name, result in orchestrator.results()`
- Critical for: Preventing 5+ simultaneous OathNet API calls on 1GB VPS

**DatabaseManager:**
- Purpose: Single-connection SQLite with safe concurrent access
- Pattern: WAL mode + asyncio.Queue serialization for writes
- Location: `api/db.py`
- Usage: `await db.startup()`, `await db.write(sql, params)`, `row = await db.read_one(sql, params)`
- Critical for: Avoiding "database is locked" under load

**OathNetClient (Singleton):**
- Purpose: Async HTTP wrapper for OathNet API
- Pattern: Single httpx.AsyncClient instance shared across all requests (TCP reuse)
- Location: `modules/oathnet_client.py`
- Usage: `await oathnet_client.search_breach(query)` returns OathnetResult dataclass
- Critical for: Connection pooling, cost optimization (Phase 11)

**SpiderFootTarget Validator:**
- Purpose: Validate FQDN and IPv4 formats before passing to SpiderFoot
- Location: `modules/spiderfoot_wrapper.py`
- Usage: Called before `_run_spiderfoot()` (line 1473)

## Entry Points

**HTTP Entry Point:**
- Location: `api/main.py` line 1
- Bootstrap: FastAPI app created at module level with lifespan management
- Lifespan: `async def lifespan()` (line 225) — handles startup (JWT validation, DB init, watchdog start) and shutdown (watchdog cancel, DB close)

**Web Entry Point:**
- Location: `static/index.html`
- Bootstrap: Runs `static/js/bootstrap.js` on page load
- Responsibilities:
  - Checks for JWT in cookie/storage
  - Redirects to login if no JWT
  - Establishes SSE listener for `/api/search` responses
  - Renders results via `static/js/render.js`

**Admin Entry Point:**
- Location: `static/admin.html`
- Bootstrap: Runs `static/js/admin.js` on load
- Requires: JWT with role="admin"
- Responsibilities: Dashboard stats, user management, log viewing

## Error Handling

**Strategy:** Exception handling by layer — catch specific exceptions, convert to HTTP status codes or SSE errors.

**Patterns:**

1. **Route Layer** (api/main.py endpoints):
   ```python
   try:
       result = await db.read_one(...)
   except aiosqlite.Error as e:
       raise HTTPException(status_code=503, detail=...)
   ```
   - Converts DB errors → HTTP 503
   - Never exposes exception detail to client (logged internally)

2. **Stream Layer** (_stream_search):
   ```python
   try:
       result = await oathnet_client.search_breach(query)
   except httpx.HTTPError as exc:
       yield event({"type": "module_error", "module": "breach", "error": str(exc)})
   ```
   - Yields SSE error event instead of raising
   - Allows remaining modules to continue
   - Incremental results still delivered to client

3. **Orchestration Layer** (TaskOrchestrator):
   ```python
   async def _guarded(coro):
       try:
           result = await coro
       except Exception as exc:
           await self._result_queue.put((name, exc))
   ```
   - Catches per-module exceptions
   - Pushes error to queue
   - Orchestrator never crashes
   - Caller receives exception object via results()

4. **Database Layer** (_writer_loop in db.py):
   ```python
   async def _writer_loop():
       try:
           await self._conn.execute(sql, params)
       except aiosqlite.Error as e:
           if future: future.set_exception(e)
   ```
   - Caller can await confirmation and handle errors
   - Fire-and-forget writes silently log errors

5. **Auth Layer** (get_current_user):
   ```python
   try:
       payload = _decode_token(token)
   except JWTError:
       raise HTTPException(status_code=401, detail="Invalid token")
   ```
   - Invalid JWT → HTTP 401
   - Expired JWT → HTTP 401
   - Blacklisted JWT → HTTP 401

**No uncaught exceptions propagate to client.** All endpoints are wrapped in `try/except` before yielding/returning response.

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module (configured at module level for each file)
- Strategy: Structured logs with module context
- Examples:
  - `logger.warning("OathNet timeout | query_hash={}", hash(query))`
  - `logger.error("DB writer failed: {}", exc_type)`
  - Never log PII — use hash() for query/target redaction
- Levels: DEBUG (disabled in production), INFO (startup/shutdown), WARNING (timeouts/retries), ERROR (unhandled exceptions)

**Rate Limiting:**
- Framework: `slowapi` (based on starlette-limiter)
- Config: Endpoint-specific via `@limiter.limit(RL_SEARCH_LIMIT)` where `RL_SEARCH_LIMIT = "10/minute"`
- Keys: IP address (fallback) or authenticated username (preferred)
- Enforcement: Returns HTTP 429 if exceeded; client should retry with `Retry-After` header
- Custom handler: `_rate_limit_handler()` (line 288) returns JSON error

**Input Validation:**
- Framework: Pydantic v2 with field validators
- Models:
  - `LoginRequest` (line 151): username (str), password (str)
  - `SearchRequest` (line 155): query (str), mode (str), modules (list[str]), limit (int)
- Validators: `field_validator` decorators check input constraints
- Strategy: **Frontend validation is cosmetic; all critical validation happens in Pydantic model on backend**

**CSRF Protection:**
- Strategy: None needed — API is token-authenticated (JWT in header), not cookie-authenticated
- Rationale: Tokens in `Authorization` header cannot be stolen by CSRF

**XSS Prevention:**
- Strategy: **No HTML escaping on backend** — all output is JSON, never HTML
- CSP enforced: `default-src 'self'` prevents inline scripts
- Frontend sanitizes all user input before rendering (`DOMPurify` or manual text content)
- Example: Breach email never rendered as `innerHTML`, only as text content

**CORS:**
- Configured: `CORSMiddleware` (line ~560 in main.py, exact line varies)
- Allow origins: `["http://localhost:3000", "https://nexus.example.com"]` (from env)
- Credentials: True (allows cookies/auth headers)
- Methods: GET, POST, PUT, DELETE
- Headers: *, but restricted to Content-Type, Authorization

**Authentication:**
- Method: JWT (HS256 algorithm, 24h expiry, stored in httpOnly cookie)
- Secret: Read from `JWT_SECRET` env var at startup
- Validation: `_validate_jwt_secret()` called in lifespan — exits process if missing or weak
- Refresh: No refresh tokens — user logs in again after 24h

**Memory Pressure Response:**
- Watched by: `memory_watchdog_loop()` in `api/watchdog.py`
- Thresholds:
  - NORMAL: mem < 75% → ceiling = 5
  - REDUCED: 75% < mem < 85% → ceiling = 2
  - CRITICAL: mem > 85% → ceiling = 0 (reject all new scans)
- Effects: Slow down module execution, not crash the process
- Reported: `/health` endpoint shows degradation_mode and active_agents count

---

*Architecture analysis: 2026-04-19*
