# Codebase Structure

**Analysis Date:** 2026-04-19

## Directory Layout

```
nexus_osint/
├── .git/                              # Git repository
├── .planning/                         # Phase planning & analysis documents
│   ├── codebase/                      # THIS DIRECTORY — architecture docs
│   ├── phases/                        # Historical phase plans and summaries
│   ├── PROJECT.md                     # Roadmap and milestone tracking
│   ├── ROADMAP.md                     # Current phase status
│   └── STATE.md                       # Session progress tracking
├── api/                               # FastAPI backend
│   ├── __init__.py                    # Empty init
│   ├── main.py                        # Monolithic FastAPI app (1770 lines)
│   ├── db.py                          # DatabaseManager — SQLite + WAL + Queue
│   ├── orchestrator.py                # TaskOrchestrator — concurrent execution
│   └── watchdog.py                    # Memory watchdog loop
├── modules/                           # External service integrations
│   ├── __init__.py                    # Empty init
│   ├── oathnet_client.py              # OathNet API wrapper (async)
│   ├── sherlock_wrapper.py            # Sherlock social platform search
│   ├── spiderfoot_wrapper.py          # SpiderFoot domain/IP recon
│   └── report_generator.py            # Legacy report generation (unused in v3.0)
├── static/                            # Frontend assets (served by nginx)
│   ├── index.html                     # Main search interface
│   ├── admin.html                     # Admin dashboard
│   ├── js/                            # Vanilla JavaScript modules
│   │   ├── bootstrap.js               # Startup logic, JWT check, SSE setup
│   │   ├── auth.js                    # Login, logout, JWT management
│   │   ├── search.js                  # Search form submission
│   │   ├── render.js                  # SSE event rendering (75KB, largest)
│   │   ├── state.js                   # Global state accumulation
│   │   ├── admin.js                   # Admin dashboard interaction
│   │   ├── cases.js                   # Case/project management UI
│   │   ├── panels.js                  # Panel lifecycle (open/close/collapse)
│   │   ├── export.js                  # Export results (CSV, JSON, PDF)
│   │   ├── history.js                 # Search history sidebar
│   │   └── utils.js                   # Shared helpers (date format, dom utils)
│   └── css/                           # Meridian design system CSS
│       ├── tokens.css                 # Design tokens (colors, spacing, typography)
│       ├── reset.css                  # Browser reset
│       ├── layout.css                 # Grid, flex, container layouts
│       ├── components.css             # Buttons, inputs, badges, pills
│       ├── panels.css                 # Panel styling
│       ├── cards.css                  # Result card variants (breach, social, etc)
│       ├── tables.css                 # Table styling
│       ├── overlays.css               # Modal, tooltip, dropdown styling
│       ├── responsive.css             # Mobile breakpoints
│       └── security-hardening.css     # CSP-compliant styles, no unsafe-inline
├── tests/                             # Test suite
│   ├── __init__.py                    # Empty init
│   ├── conftest.py                    # pytest fixtures
│   ├── unit/                          # Unit tests (no I/O)
│   │   ├── __init__.py
│   │   └── test_security_gates.py     # Auth, rate limiting, input validation
│   ├── integration/                   # Integration tests
│   │   ├── __init__.py
│   │   └── test_rate_limiting.py      # Slowapi rate limit verification
│   ├── test_db.py                     # DatabaseManager tests
│   ├── test_db_stream.py              # Streaming DB query tests
│   ├── test_endpoints.py              # FastAPI endpoint tests
│   ├── test_oathnet_client.py         # OathNet async client tests
│   └── test_orchestrator.py           # TaskOrchestrator tests
├── docker-compose.yml                 # Multi-container setup (api + spiderfoot + nginx)
├── Dockerfile                         # Multi-stage build for api container
├── nginx.conf                         # Reverse proxy config (security headers, compression)
├── entrypoint.sh                      # Container startup script
├── requirements.txt                   # Production Python dependencies
├── requirements-dev.txt               # Development-only dependencies
├── pytest.ini                         # pytest configuration
├── CLAUDE.md                          # Project-specific Claude instructions (27KB)
├── DEPLOY.md                          # Manual deployment guide
├── nexus_osint.db*                    # SQLite database + WAL/SHM files
└── .gitignore                         # Excludes: .env, *.pyc, __pycache__, db files
```

## Directory Purposes

**`api/`:**
- Purpose: FastAPI backend application
- Contains: HTTP route handlers, database access, authentication, orchestration
- Key files: `main.py` (monolith to be refactored), `db.py` (database layer), `orchestrator.py` (concurrency control)
- Run: `uvicorn api.main:app --host 0.0.0.0 --port 8000`

**`modules/`:**
- Purpose: External service client wrappers and utilities
- Contains: OathNet API client, Sherlock CLI wrapper, SpiderFoot integration
- Key files: Each module exports one or more async functions / classes
- Pattern: Each module handles its own error handling and returns dataclasses (never raises to caller except in orchestrator-caught context)

**`static/`:**
- Purpose: Frontend UI (pure Vanilla JS, no framework)
- Contains: HTML templates, CSS design system, JavaScript application logic
- Key files: `index.html` (main), `js/render.js` (75KB, handles result display), `js/state.js` (global state)
- Served by: nginx reverse proxy at `/` and `/admin` (static files cached)
- Design: Amber/Noir color scheme via `css/tokens.css` (Meridian design system)

**`tests/`:**
- Purpose: Automated testing
- Organized by: unit/ (no I/O), integration/ (with services), root level (mixed)
- Key files: `conftest.py` (pytest fixtures), `test_endpoints.py` (FastAPI TestClient)
- Run: `pytest tests/ -v --tb=short`

**`.planning/`:**
- Purpose: GSD (Get Shit Done) phase planning and documentation
- Subdirs:
  - `codebase/` ← Output location for this analysis (ARCHITECTURE.md, STRUCTURE.md)
  - `phases/` — Historical phase plans (F1 Audit, F4 SQLite Hardening, etc)
  - `research/` — Technical research notes
- Key files: `ROADMAP.md` (milestone status), `STATE.md` (session checkpoint)

## Key File Locations

**Entry Points:**

| File | Purpose | Trigger |
|------|---------|---------|
| `api/main.py` | FastAPI app | `uvicorn api.main:app` |
| `static/index.html` | Search UI | Browser GET `/` |
| `static/admin.html` | Admin panel | Browser GET `/admin` |
| `api/db.py` | Database init | Called in `main.py` lifespan |

**Configuration:**

| File | Purpose | Contains |
|------|---------|----------|
| `docker-compose.yml` | Service orchestration | API container, SpiderFoot, nginx config |
| `nginx.conf` | Reverse proxy config | Security headers, gzip, static file caching |
| `requirements.txt` | Python dependencies | fastapi, aiosqlite, httpx, python-jose, bcrypt, slowapi, cachetools |
| `pytest.ini` | Test config | asyncio_mode, markers |
| `.env` (git-ignored) | Secrets | JWT_SECRET, OATHNET_API_KEY, SPIDERFOOT_URL, APP_PASSWORD |

**Core Logic:**

| File | Key Functions/Classes | Lines |
|------|----------------------|-------|
| `api/main.py` | FastAPI app, route handlers, auth, caching, logging | 1770 |
| `api/db.py` | DatabaseManager class | 327 |
| `api/orchestrator.py` | TaskOrchestrator, DegradationMode, get_orchestrator | 233 |
| `api/watchdog.py` | memory_watchdog_loop(), _decide_mode() | 150 |
| `modules/oathnet_client.py` | OathNetClient class, async methods, dataclasses | ~500 |
| `modules/sherlock_wrapper.py` | search_username() async wrapper | ~350 |
| `modules/spiderfoot_wrapper.py` | SpiderFootTarget class, _run_scan() | ~600 |

**Testing:**

| File | Coverage | Lines |
|------|----------|-------|
| `tests/test_db.py` | DatabaseManager read/write | ~150 |
| `tests/test_db_stream.py` | DatabaseManager streaming queries | ~140 |
| `tests/test_orchestrator.py` | TaskOrchestrator submit/results | ~200 |
| `tests/test_endpoints.py` | FastAPI TestClient on sample routes | ~100 |
| `tests/unit/test_security_gates.py` | Auth, rate limiting, validators | ~150 |

**Styling:**

| File | Purpose | Size |
|------|---------|------|
| `css/tokens.css` | Design system variables (Amber/Noir) | ~5KB |
| `css/cards.css` | Result card variants | ~32KB |
| `css/panels.css` | Result panel layout | ~14KB |

## Naming Conventions

**Files:**
- Backend Python: `snake_case.py` — `oathnet_client.py`, `main.py`, `test_db.py`
- Frontend HTML: `index.html`, `admin.html`
- Frontend JS: `snake_case.js` — `bootstrap.js`, `render.js`, `state.js`
- CSS: `kebab-case.css` — `tokens.css`, `layout.css`, `security-hardening.css`

**Directories:**
- Backend: lowercase singular/plural — `api/`, `modules/`, `tests/`
- Static assets: lowercase — `static/js/`, `static/css/`
- Planning: `.planning/codebase/`, `.planning/phases/`

**Functions:**
- Private (internal): leading underscore — `_stream_search()`, `_save_quota()`, `_load_users()`
- Public (exported): no leading underscore — `detect_type()`, `get_current_user()`, `search_username()`
- Async: `async def` keyword — `async def lifespan()`, `async def _stream_search()`

**Classes:**
- PascalCase — `DatabaseManager`, `TaskOrchestrator`, `OathNetClient`, `LoginRequest`
- Dataclasses (data transfer): `BreachRecord`, `OathnetMeta`, `SearchRequest`
- Exceptions: inherits from BaseException or custom base (not used in v3.0)

**Variables:**
- Module-level constants: UPPERCASE — `JWT_ALGORITHM`, `RL_SEARCH_LIMIT`, `MAX_USERS`
- Local variables: lowercase snake_case — `query`, `scan_result`, `is_email`
- Private: leading underscore — `_db`, `_sentinel_done`, `_weak_jwt_secrets`

**API Routes:**
- Pattern: `/api/{resource}/{action}` or `/api/{resource}`
- Examples:
  - `/api/search` — POST, stream SSE
  - `/api/auth/login` — POST, return JWT
  - `/api/admin/stats` — GET, return dashboard stats
  - `/api/admin/logs` — GET, return audit logs
  - `/health` — GET, return status (no auth required)
  - `/sf/status` — GET, return SpiderFoot status

## Where to Add New Code

**New OSINT Module (e.g., Hunter.io lookup):**
1. Create `modules/hunter_wrapper.py`
2. Implement async wrapper: `async def search_email_on_hunter(email: str) -> HunterResult:`
3. Add to module selection in `_stream_search()` around line 842 (run dict)
4. Add module execution block in `_stream_search()` (follow Sherlock pattern around line 1023)
5. Add to test coverage: `tests/test_hunter_wrapper.py`

**New Admin Endpoint (e.g., user quota adjustment):**
1. Add route handler in `api/main.py` (after line 1401, with other admin endpoints)
2. Decorator: `@app.post("/api/admin/quota-adjust")` + `@limiter.limit(RL_ADMIN_LIMIT)`
3. Dependency: `_: dict = Depends(get_admin_user)`
4. Database: Use `await db.write_await()` for persistence
5. Test: Add to `tests/test_endpoints.py` with admin user fixture

**New Frontend Component (e.g., result filter sidebar):**
1. Add HTML structure to `static/index.html` (find appropriate panel or create new `<section>`)
2. Add styling: Create new rule in `static/css/components.css` or `static/css/panels.css`
3. Add JS logic: Create new module or add to existing (`static/js/panels.js` if layout-related)
4. State: Update `g_state` schema in `static/js/state.js` if new data structure needed
5. Rendering: Add handler in `static/js/render.js` to populate component from state

**Database Migration (e.g., add new audit field):**
1. Modify `api/db.py` line 129+ in `_create_schema()` (ALTER TABLE for existing DB)
2. Handle backward compatibility: `CREATE TABLE IF NOT EXISTS` + column existence check
3. Update `_log_search()` in `api/main.py` to populate new field (line 505)
4. Test: Run against existing DB file to verify no "database is locked" during migration

**New Dependency:**
1. Add to `requirements.txt` with pinned version
2. Update `requirements-dev.txt` if development-only
3. Docker: Rebuild with `docker build -t nexus .`
4. Verify image size stays < 250MB: `docker images nexus`

**New Test:**
1. Choose directory: `tests/unit/` (no I/O), `tests/integration/` (with services), or root (mixed)
2. Naming: `test_<module>.py` for module tests, `test_<function>.py` for unit tests
3. Fixtures: Use `conftest.py` fixtures or create in-file
4. Async: Use `@pytest.mark.asyncio` decorator
5. Run: `pytest tests/test_new.py -v`

## Special Directories

**`.planning/codebase/`:**
- Purpose: Architecture documentation for Phase 15 refactor planning
- Generated: By `/gsd:map-codebase arch` command
- Committed: Yes
- Content:
  - `ARCHITECTURE.md` — Layer descriptions, data flows, abstractions
  - `STRUCTURE.md` — Directory tree, file purposes, naming conventions
  - (Output of this exploration)

**`.planning/phases/`:**
- Purpose: Phase execution plans and summaries
- Generated: By `/gsd:plan-phase` command per feature
- Committed: Yes
- Subdirs: One per phase (01-meridian-css, 04-sqlite-hardening, 15-refactor-main-py-layers, etc)
- Each phase contains: PLAN.md (detailed steps), SUMMARY.md (what happened), CONTEXT.md (decisions), DISCUSSION-LOG.md (chat history)

**`__pycache__/` and `.pytest_cache/`:**
- Purpose: Python and pytest caches
- Generated: Automatically at runtime
- Committed: No (in .gitignore)
- Cleanup: `rm -rf __pycache__ .pytest_cache` before commits

**`nexus_osint.db*`:**
- Purpose: SQLite database files (data + WAL + shared memory)
- Generated: At first app startup
- Committed: No (in .gitignore)
- Lifecycle: Persistent across restarts; survives container restart if volume-mounted

---

## Import Dependency Map

**Intra-api imports:**

| From | Imports | Usage |
|------|---------|-------|
| `api/main.py` | `from api.db import db` | All DB reads/writes |
| `api/main.py` | `from api.orchestrator import get_orchestrator, DegradationMode` | Submitting concurrent modules, health checks |
| `api/main.py` | `from api.watchdog import memory_watchdog_loop` | Started in lifespan |
| `api/orchestrator.py` | (none from api/) | Standalone |
| `api/db.py` | (none from api/) | Standalone |
| `api/watchdog.py` | `from api.orchestrator import get_orchestrator, DegradationMode` | Monitors and adjusts ceiling |

**Intra-modules imports:**

| From | Imports | Usage |
|------|---------|-------|
| `api/main.py` | `from modules.oathnet_client import oathnet_client` | Calls `oathnet_client.search_breach()`, etc |
| `api/main.py` | `from modules.sherlock_wrapper import search_username` | Calls `search_username()` |
| `api/main.py` | `from modules.spiderfoot_wrapper import SpiderFootTarget` | Validates target, calls `_run_spiderfoot()` |
| `modules/oathnet_client.py` | (none from modules/) | Standalone |
| `modules/sherlock_wrapper.py` | (none from modules/) | Standalone |
| `modules/spiderfoot_wrapper.py` | (none from modules/) | Standalone |
| `modules/report_generator.py` | (possibly others, but unused in v3.0) | Legacy |

**External imports (top dependencies):**
- `fastapi`, `starlette` — HTTP framework
- `aiosqlite` — Async SQLite
- `httpx` — Async HTTP client
- `python-jose`, `bcrypt` — JWT + password hashing
- `slowapi` — Rate limiting
- `cachetools` — TTL caching
- `psutil` — Memory monitoring
- `pydantic` — Input validation

## No Circular Imports

The dependency graph is **acyclic**:
- `api/main.py` → `api/db.py` (one direction)
- `api/main.py` → `api/orchestrator.py` (one direction)
- `api/watchdog.py` → `api/orchestrator.py` (one direction)
- `api/main.py` → `modules/*` (one direction)

Safe to import freely without risk of circular dependency errors.

---

## Phase 15 Refactor Target

Current monolith `api/main.py` (1770 lines) will be split into:

```
api/
├── main.py                 # HTTP app setup, middleware, lifespan (remove routes)
├── routes/
│   ├── __init__.py
│   ├── auth.py            # /api/auth/* endpoints
│   ├── search.py          # /api/search endpoint (move _stream_search here)
│   ├── admin.py           # /api/admin/* endpoints
│   ├── health.py          # /health, /sf/status endpoints
│   └── victims.py         # /api/victims/* endpoints
├── services/
│   ├── __init__.py
│   ├── search_service.py  # Search orchestration (move _stream_search logic)
│   ├── auth_service.py    # JWT, user management (_verify_user, _create_token, etc)
│   └── admin_service.py   # Stats, logs, user CRUD
├── repositories/
│   ├── __init__.py
│   ├── search_repository.py   # Insert/query searches table
│   ├── auth_repository.py     # Token blacklist, users file I/O
│   └── quota_repository.py    # Quota log CRUD
├── models/
│   ├── __init__.py
│   ├── requests.py        # Pydantic models (LoginRequest, SearchRequest)
│   ├── responses.py       # Response dataclasses
│   └── domain.py          # Domain models (User, Search, Token)
├── core/
│   ├── __init__.py
│   ├── config.py          # Constants, env var loading
│   ├── security.py        # JWT secret validation, decorators
│   ├── exceptions.py      # Custom exception types
│   └── dependencies.py    # Dependency injection (get_current_user, etc)
└── utils/
    ├── __init__.py
    ├── caching.py         # _get_cached, _set_cached, TTLCache
    ├── serializers.py     # _serialize_breaches, _serialize_stealers
    ├── detectors.py       # detect_type, _parse_discord_history
    └── validators.py      # _validate_id, input validators
```

**Safe extraction order (avoid import cycles):**
1. `models/` — No dependencies, base data types
2. `core/` — Config, security, custom exceptions
3. `repositories/` — Depends on core only
4. `services/` — Depends on repositories + models
5. `routes/` — Depends on services + models
6. `utils/` — Helpers, no circular
7. Update `main.py` — Include routers, remove inline code

*Structure analysis: 2026-04-19*
