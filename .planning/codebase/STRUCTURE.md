# Codebase Structure

**Analysis Date:** 2026-03-25

## Directory Layout

```
nexus_osint/
├── api/                        # FastAPI backend (Python)
│   ├── __init__.py             # Empty package marker
│   └── main.py                 # Monolith backend — all routes, models, auth, middleware (1262 lines)
├── modules/                    # OSINT data source wrappers (Python)
│   ├── __init__.py             # Empty package marker
│   ├── oathnet_client.py       # OathNet API client — breaches, stealers, Discord, gaming (545 lines)
│   ├── sherlock_wrapper.py     # Social media username checker — 25+ platforms (393 lines)
│   ├── report_generator.py     # HTML/PDF report generation — NOT integrated in main.py (839 lines)
│   └── spiderfoot_wrapper.py   # SpiderFoot CLI wrapper — deep OSINT scans (530 lines)
├── static/                     # Frontend — vanilla HTML/CSS/JS (no build step)
│   ├── index.html              # Main SPA shell — HTML structure only (361 lines)
│   ├── admin.html              # Admin panel — self-contained monolith with inline CSS/JS (1426 lines)
│   ├── css/                    # Modular CSS files (9 files, extracted from former monolith)
│   │   ├── tokens.css          # Meridian design system — all CSS custom properties (155 lines)
│   │   ├── reset.css           # Box-sizing, scrollbar, body base, grid texture (70 lines)
│   │   ├── layout.css          # Page wrapper, nav bar, hero section (117 lines)
│   │   ├── components.css      # Search, buttons, toggles, chips, badges, inputs (213 lines)
│   │   ├── panels.css          # Quota bars, scan status, collapsible result panels, stat cards (290 lines)
│   │   ├── tables.css          # Data tables, severity rows, password cells, social grid (104 lines)
│   │   ├── cards.css           # Discord profile, gaming, victim, history cards (377 lines)
│   │   ├── overlays.css        # Auth screen, cases panel, file viewer modal, toast (170 lines)
│   │   └── responsive.css      # All @media queries consolidated (63 lines)
│   └── js/                     # Modular JS files (9 files, extracted from former monolith)
│       ├── state.js            # Global state, constants (CATEGORIES, MOD_LABELS), init() (53 lines)
│       ├── utils.js            # esc(), escAttr(), detectType(), onQueryInput(), riskLabel() (74 lines)
│       ├── auth.js             # JWT auth — checkAuth, submitAuth, signOut, apiFetch (118 lines)
│       ├── search.js           # SSE search — startSearch, mode/chip builders, SpiderFoot check (202 lines)
│       ├── render.js           # DOM rendering — results, breaches, stealers, social, victims (930 lines)
│       ├── panels.js           # Scan progress, panel toggle, panel visibility, quota UI (140 lines)
│       ├── export.js           # Export — JSON, CSV, TXT, PDF generation, clipboard copy (735 lines)
│       ├── cases.js            # Case management — save, load, delete, localStorage persistence (127 lines)
│       └── history.js          # Search history — save, render, rerun from localStorage (43 lines)
├── Dockerfile                  # Python 3.11-slim, gosu, uvicorn (28 lines)
├── docker-compose.yml          # 3 services: nexus (FastAPI), nginx (reverse proxy), certbot (SSL) (87 lines)
├── nginx.conf                  # HTTPS, TLS 1.2/1.3, HSTS, CSP, rate limiting zones (101 lines)
├── entrypoint.sh               # Permission fix + gosu uvicorn launch (5 lines)
├── requirements.txt            # Python dependencies — 13 packages (13 lines)
├── __init__.py                 # Empty root package marker
├── .dockerignore               # Excludes secrets, tests, docs, IDE files from image
├── .gitignore                  # Excludes .env, cases.json, __pycache__, logs, exports
├── README.md                   # Original README (still references Streamlit — outdated)
├── ai-context.md               # Comprehensive project context doc for AI assistants (large)
└── BRIEFING_IMPLEMENTACAO.md   # Phase 1-4 implementation plan from audit session (539 lines)
```

## Directory Purposes

**`api/`**
- Purpose: FastAPI backend — all server-side logic
- Contains: Single monolith file `main.py` with all routes, models, auth, middleware, helpers
- Key file: `api/main.py` (1262 lines) — the entire backend
- Mounted read-only in Docker: `./api:/app/api:ro`

**`modules/`**
- Purpose: OSINT data source integrations — each wrapper is independent
- Contains: Python modules that `api/main.py` imports for search operations
- Mounted read-only in Docker: `./modules:/app/modules:ro`
- Note: `report_generator.py` exists but is NOT imported or used by `api/main.py`

**`static/`**
- Purpose: Frontend assets served by FastAPI's `StaticFiles` middleware
- Contains: HTML pages, CSS, and JavaScript — no build toolchain
- Mounted read-only in Docker: `./static:/app/static:ro`
- Served at `/` (index.html) and `/admin` (admin.html)

**`static/css/`**
- Purpose: Modular CSS extracted from the former 4384-line index.html monolith (Phase 1 refactor)
- Contains: 9 CSS files loaded in dependency order via `<link>` tags
- Load order matters: tokens -> reset -> layout -> components -> panels -> tables -> cards -> overlays -> responsive
- Total: 1559 lines of CSS across 9 files

**`static/js/`**
- Purpose: Modular JavaScript extracted from the former index.html monolith (Phase 1 refactor)
- Contains: 9 JS files loaded in dependency order via `<script>` tags
- Load order matters: state -> utils -> auth -> search -> render -> panels -> export -> cases -> history
- Total: 2422 lines of JavaScript across 9 files
- All functions and variables live in global scope (no module system, no bundler)

**`data/` (runtime only — not in repo)**
- Purpose: Persistent data directory created at container startup
- Contains: `users.json` (user accounts), `audit.db` (SQLite audit log)
- Path inside container: `/app/data`
- Docker volume: `nexus_data` mounted at `/app/data`

## Key File Locations

**Entry Points:**
- `api/main.py`: Backend entry — `uvicorn api.main:app` launched by `entrypoint.sh`
- `static/index.html`: Frontend entry — served at `/` by FastAPI
- `static/admin.html`: Admin panel — served at `/admin` by FastAPI
- `static/js/state.js`: Frontend initialization — contains `init()` function called on page load

**Configuration:**
- `docker-compose.yml`: Service orchestration, environment variables, volume mounts, network setup
- `nginx.conf`: Reverse proxy config, SSL, security headers, rate limiting zones
- `Dockerfile`: Build instructions — Python 3.11-slim base, user creation, permissions
- `entrypoint.sh`: Container startup — permission fix, then `gosu appuser uvicorn`
- `requirements.txt`: Python package manifest (13 dependencies)
- `.env`: Runtime secrets (not in repo) — `OATHNET_API_KEY`, `JWT_SECRET`, `APP_PASSWORD`, etc.

**Core Backend Logic:**
- `api/main.py` lines 1-65: Config, environment loading, constants
- `api/main.py` lines 66-105: Pydantic models (LoginRequest, SearchRequest)
- `api/main.py` lines 107-290: Auth system (JWT, bcrypt, user management, rate limiting)
- `api/main.py` lines 293-374: Audit DB, security middleware, startup event
- `api/main.py` lines 376-914: Route handlers (root, auth, login, search with SSE streaming)
- `api/main.py` lines 916-1070: Admin endpoints (stats, logs, user CRUD)
- `api/main.py` lines 1073-1262: SpiderFoot, Discord history, victims, health check

**OSINT Modules:**
- `modules/oathnet_client.py`: OathNet API wrapper — breach search, stealer search, Discord, gaming, holehe
- `modules/sherlock_wrapper.py`: Username checker — async HTTP checks across 25+ platforms with CLI fallback
- `modules/spiderfoot_wrapper.py`: SpiderFoot CLI integration — subprocess-based, passive/footprint/investigate modes
- `modules/report_generator.py`: HTML and PDF report generation (NOT currently wired into the backend)

**Frontend — CSS (load order):**
- `static/css/tokens.css`: Design tokens — Meridian system v1.0 (surfaces, borders, accent, severity, text, typography, spacing, radius, shadows, transitions, z-index)
- `static/css/reset.css`: Global reset, body base styles, grid texture background
- `static/css/layout.css`: `.page` wrapper (960px max), `.nav` sticky bar, `.hero` section
- `static/css/components.css`: `.search-container`, `.btn`, `.toggle`, `.chip`, `.badge`, `.input`, `kbd`
- `static/css/panels.css`: `.quota-bar`, `.quota-pill`, `.scan-status`, `.panel` (collapsible), `.stat-card`
- `static/css/tables.css`: `.data-table`, severity row classes (`.sev-critical`, `.sev-high`, etc.), `.social-grid`
- `static/css/cards.css`: `.discord-card`, `.gaming-card`, `.victim-card`, `.history-card`
- `static/css/overlays.css`: `.toast`, `.auth-screen`, `.auth-card`, `.cases-panel`, `.file-viewer`
- `static/css/responsive.css`: All `@media` queries — 640px and 600px breakpoints

**Frontend — JS (load order):**
- `static/js/state.js`: Global vars (`mode`, `sfMode`, `selectedMods`, `currentResult`, `history`, `quotaData`), constants (`CATEGORIES`, `MOD_LABELS`), `init()`
- `static/js/utils.js`: `TYPE_LABELS`, `detectType()`, `onQueryInput()`, `riskLabel()`, `esc()`, `escAttr()`
- `static/js/auth.js`: `authToken`, `authUser`, `authHeaders()`, `apiFetch()`, `checkAuth()`, `submitAuth()`, `signOut()`, `renderNavUser()`
- `static/js/search.js`: `checkSpiderFoot()`, `setMode()`, `setSfMode()`, `buildCatChips()`, `buildModChips()`, `startSearch()` with SSE EventSource
- `static/js/render.js`: `renderResults()`, `renderBreaches()`, `renderStealers()`, `renderSocial()`, `renderExtras()`, Discord/gaming/victim card builders, file viewer
- `static/js/panels.js`: `setScanProgress()`, `addModuleRow()`, `markModuleDone()`, `applyPanelVisibility()`, `togglePanel()`, `showToast()`
- `static/js/export.js`: `copySection()`, `copyAll()`, `exportJSON()`, `exportCSV()`, `exportTXT()`, `exportPDF()` (client-side PDF generation)
- `static/js/cases.js`: `toggleCasesPanel()`, `saveCase()`, `deleteCase()`, `clearAllCases()`, `renderCasesPanel()`, `updateCasesBadge()`, `loadCase()`
- `static/js/history.js`: `saveHistory()`, `renderHistory()`, `rerunSearch()`

## Naming Conventions

**Files:**
- Python: `snake_case.py` — e.g., `oathnet_client.py`, `sherlock_wrapper.py`, `report_generator.py`
- CSS: `lowercase.css` — single-word names e.g., `tokens.css`, `reset.css`, `components.css`
- JS: `lowercase.js` — single-word names e.g., `state.js`, `auth.js`, `render.js`
- HTML: `lowercase.html` — e.g., `index.html`, `admin.html`
- Config: `lowercase` with appropriate extension — `nginx.conf`, `docker-compose.yml`

**Directories:**
- All lowercase, no hyphens: `api/`, `modules/`, `static/`, `css/`, `js/`

**CSS Classes:**
- BEM-lite with hyphens: `.search-container`, `.panel-header`, `.stat-card-val`
- Severity prefixes: `.sev-critical`, `.sev-high`, `.sev-medium`, `.sev-low`
- State classes: `.active`, `.visible`, `.open`, `.copied`, `.saved`
- Domain-specific prefixes: `.discord-*`, `.gaming-*`, `.victim-*`, `.history-*`

**JavaScript:**
- Functions: `camelCase` — `startSearch()`, `renderResults()`, `toggleCasesPanel()`
- Global variables: `camelCase` — `currentResult`, `selectedMods`, `authToken`
- Constants: `UPPER_SNAKE_CASE` — `CATEGORIES`, `MOD_LABELS`, `TYPE_LABELS`, `BREACH_PAGE_SIZE`

**Python (backend):**
- Functions: `snake_case` — `detect_type()`, `_check_rate()`, `_log_search()`
- Private functions: `_prefix` — `_serialize_breaches()`, `_validate_id()`, `_parse_discord_history()`
- Constants: `UPPER_SNAKE_CASE` — `OATHNET_API_KEY`, `JWT_SECRET`, `AUDIT_DB`
- Classes: `PascalCase` — `LoginRequest`, `SearchRequest`, `SecurityHeadersMiddleware`

## Where to Add New Code

**New API endpoint:**
- Add to `api/main.py` — group with related endpoints (admin routes at ~line 916+, search-related at ~line 494+)
- Use `@app.get()` or `@app.post()` decorators
- Protect with `Depends(get_current_user)` or `Depends(get_admin_user)`
- No separate route files exist; everything goes in `main.py`

**New OSINT module/wrapper:**
- Create `modules/<service_name>_wrapper.py` or `modules/<service_name>_client.py`
- Follow the dataclass pattern from `oathnet_client.py` for result types
- Import it in `api/main.py` inside the relevant search function
- Add SSE event emission in the `_stream_search()` generator function

**New frontend feature (UI section):**
- HTML structure: Add to `static/index.html` (keep it thin — only HTML, no inline styles/scripts)
- Styling: Add CSS to the most relevant file in `static/css/` — match the component type
- Logic: Add a new JS file in `static/js/` or extend an existing one
- Add `<script src="js/newfile.js"></script>` in `static/index.html` before the closing `</body>` tag
- Respect the load order: new file must come after its dependencies

**New CSS component:**
- Determine which file it belongs in based on type:
  - Base UI elements (buttons, inputs, chips): `static/css/components.css`
  - Data display (tables, grids): `static/css/tables.css`
  - Domain-specific cards: `static/css/cards.css`
  - Collapsible/stateful panels: `static/css/panels.css`
  - Fullscreen/modal/floating: `static/css/overlays.css`
- Use tokens from `static/css/tokens.css` — never hardcode colors, spacing, or radii

**New export format:**
- Add to `static/js/export.js` — follow the pattern of `exportJSON()`, `exportCSV()`, etc.
- Add a button in the export panel HTML in `static/index.html` (around line 172)

**New admin feature:**
- Backend: Add endpoint in `api/main.py` with `Depends(get_admin_user)`
- Frontend: Modify `static/admin.html` directly (it is a self-contained monolith with inline CSS/JS)

## Special Directories

**`data/` (runtime, not in repo):**
- Purpose: Persistent storage for users and audit data
- Generated: Yes, at container startup by `Dockerfile` (`mkdir -p data`)
- Committed: No (does not exist in repo; lives in Docker volume `nexus_data`)
- Contains: `users.json`, `audit.db`

**`.planning/` (development only):**
- Purpose: AI assistant planning and analysis documents
- Generated: Yes, by GSD mapping commands
- Committed: Not yet (untracked in git status)
- Contains: `codebase/` with analysis markdown files

**`__pycache__/` (runtime, not in repo):**
- Purpose: Python bytecode cache
- Generated: Yes, automatically by Python
- Committed: No (in `.gitignore`)

## File Size Distribution

| Category | Files | Total Lines | Largest File |
|----------|-------|-------------|--------------|
| Backend | 1 | 1262 | `api/main.py` (1262) |
| Modules | 4 | 2307 | `modules/report_generator.py` (839) |
| Frontend HTML | 2 | 1787 | `static/admin.html` (1426) |
| Frontend CSS | 9 | 1559 | `static/css/cards.css` (377) |
| Frontend JS | 9 | 2422 | `static/js/render.js` (930) |
| Config/Infra | 5 | 234 | `nginx.conf` (101) |
| **Total** | **30** | **9571** | |

## Docker Mount Architecture

The Docker setup separates code (read-only) from data (read-write):

```
Host                          Container (/app)
─────────────────────────     ────────────────────
./api/          ──(ro)──>     /app/api/
./modules/      ──(ro)──>     /app/modules/
./static/       ──(ro)──>     /app/static/
nexus_data vol  ──(rw)──>     /app/data/
```

This means code changes on the host are reflected immediately (no rebuild needed), but `data/` persists across container restarts via Docker volume.

---

*Structure analysis: 2026-03-25*
