# Technology Stack

**Analysis Date:** 2026-03-25

## Languages

**Primary:**
- Python 3.11 — Backend API, all modules (`api/main.py`, `modules/`)
- JavaScript (ES2020+, no framework) — Frontend SPA (`static/js/`)
- HTML/CSS — Frontend markup and styling (`static/index.html`, `static/css/`)

## Runtime

**Environment:**
- Python 3.11 (slim Docker image: `python:3.11-slim`)
- Browser (vanilla JS, no build step required)

**Package Manager:**
- pip (no version pinned)
- Lockfile: absent — `requirements.txt` with pinned versions only

## Frameworks

**Core:**
- FastAPI 0.115.0 — HTTP API server, SSE streaming, static file serving
- Uvicorn 0.30.6 (with `[standard]` extras) — ASGI server, launched via `entrypoint.sh`
- Pydantic 2.8.2 — Request/response validation, field validators
- Starlette (transitive via FastAPI) — Middleware base

**Testing:**
- None detected — no test framework configured, no test files present

**Build/Dev:**
- No build step — frontend is raw HTML/CSS/JS, served as static files
- Docker + docker-compose for containerised deployment
- Nginx (Alpine image) as reverse proxy with SSL termination

## Key Dependencies

**Critical:**
- `python-jose[cryptography]==3.3.0` — JWT token creation and verification (HS256)
- `bcrypt==4.2.1` — Password hashing (used directly, bypassing passlib)
- `aiosqlite==0.20.0` — Async SQLite for audit log, rate limiter, quota tracking
- `httpx==0.27.2` — Async HTTP client used in SpiderFoot polling loop
- `aiohttp==3.10.5` — Async HTTP used in `sherlock_wrapper.py` platform checks
- `requests==2.32.3` — Sync HTTP used in `oathnet_client.py` (wrapped via `asyncio.to_thread`)

**Infrastructure:**
- `python-dotenv==1.0.1` — Loads `.env` into environment at startup
- `aiofiles==24.1.0` — Async file I/O
- `tenacity==8.5.0` — Retry logic (imported in requirements, not yet wired to OathNet calls)

## Configuration

**Environment:**
- All config loaded from `.env` via `python-dotenv` in `api/main.py`
- Required vars: `OATHNET_API_KEY`, `JWT_SECRET`
- Optional vars: `APP_PASSWORD` (legacy single-user), `ALLOWED_ORIGINS`, `LOG_LEVEL`, `JWT_EXPIRE_HOURS`, `SPIDERFOOT_URL`, `SPIDERFOOT_PATH`, `SPIDERFOOT_TIMEOUT`
- If `JWT_SECRET` is absent, an ephemeral secret is derived at startup — tokens invalidated on restart

**Build:**
- `Dockerfile` — Python 3.11-slim base, non-root `appuser` (uid 1000), exposes port 8000
- `docker-compose.yml` — Defines `nexus` (app), `nginx` (proxy), `certbot` (SSL renewal) services
- `nginx.conf` — HTTP→HTTPS redirect, TLS 1.2/1.3, rate zones: `api` 30r/m, `search` 5r/m
- `entrypoint.sh` — Drops to `appuser` via `gosu`, launches `uvicorn api.main:app --proxy-headers`

## Platform Requirements

**Development:**
- Docker + docker-compose (standard deployment path)
- Python 3.11+ if running locally without Docker
- `.env` file with `OATHNET_API_KEY` and `JWT_SECRET`

**Production:**
- Docker host with ports 80/443 exposed
- Let's Encrypt certificates managed by `certbot` container
- Domain: `nexusosint.uk` (hardcoded in `nginx.conf`)
- Persistent Docker volume `nexus_data` at `/app/data` — stores `users.json`, `audit.db`
- Optional: SpiderFoot instance reachable at `SPIDERFOOT_URL` (default `http://spiderfoot:5001`) — not included in `docker-compose.yml`

---

*Stack analysis: 2026-03-25*
