# Technology Stack

**Analysis Date:** 2026-04-19

## Languages

**Primary:**
- Python 3.12 — Backend runtime for FastAPI server, agent orchestration, database operations
- JavaScript (Vanilla) — Frontend UI, no frameworks (Vue/React/Svelte)

**Secondary:**
- YAML — Docker Compose configuration
- Bash — Entrypoint scripts, deployment helpers
- HTML/CSS — Frontend templates (meridian.css design system)

## Runtime

**Environment:**
- Python 3.12-slim (Docker base image: `python:3.12-slim`)
- Node.js — Not used; no JavaScript compilation pipeline
- asyncio (Python stdlib) — Concurrent task orchestration for OSINT agents

**Package Manager:**
- pip — Python dependency management
- Lockfile: `requirements.txt` present, maintained, pinned versions

## Frameworks

**Core:**
- FastAPI 0.115.0 — Web framework for REST API, SSE streaming, health checks
- Uvicorn 0.30.6 — ASGI server, single worker (1 process on 1vCPU VPS), asyncio-native

**Testing:**
- pytest — Unit/integration test runner
- pytest.ini — Test discovery config at `pytest.ini`
- respx — HTTP mocking for external API tests (httpx client)
- No formal test runner specified; manual execution via pytest

**Build/Dev:**
- Docker 20+ — Multi-stage builds for <250MB image
- Docker Compose 3.8+ — Local orchestration of nexus + nginx + certbot
- Nginx (Alpine) — Reverse proxy, SSL/TLS termination, static asset serving

## Key Dependencies

**Critical:**
- aiosqlite 0.20.0 — Async SQLite driver with WAL mode, single-connection pattern
- httpx 0.27.2 — Async HTTP client for outbound OSINT agent calls, connection pooling
- pydantic 2.8.2 — Input validation via models, security validator decorators
- PyJWT 2.9.0 — JWT token signing/verification for authentication
- bcrypt 4.2.1 — Password hashing for multi-user auth

**Infrastructure:**
- slowapi 0.1.9 — Rate limiting per endpoint and per-user, integrates with FastAPI
- psutil 6.0.0 — Memory/CPU monitoring for watchdog thresholds
- cachetools 5.5.0 — TTL-based response caching (5-min TTL, 200-entry limit)
- python-dotenv 1.0.1 — Environment variable loading from `.env` file
- aiofiles 24.1.0 — Async file operations (static asset serving fallback)

## Configuration

**Environment:**
- `.env` file (not committed) — Required env vars:
  - `OATHNET_API_KEY` — OathNet breach API authentication
  - `JWT_SECRET` — Secret for JWT signing (validated at startup, rejects weak defaults)
  - `APP_PASSWORD` — Legacy single-user fallback (optional)
  - `SPIDERFOOT_URL` — URL to SpiderFoot instance (default: `http://spiderfoot:5001`)
  - `JWT_EXPIRE_HOURS` — Token TTL (default: 24)
  - `LOG_LEVEL` — Logging level (default: WARNING)
  - `MAX_USERS` — User cap for admin panel (default: 50)
  - `ALLOWED_ORIGINS` — CORS allowed origins (default: `https://nexusosint.uk`)
  - `RL_LOGIN_LIMIT`, `RL_REGISTER_LIMIT`, `RL_SEARCH_LIMIT`, `RL_SPIDERFOOT_LIMIT`, `RL_ADMIN_LIMIT`, `RL_READ_LIMIT` — Rate limit strings (e.g., "5/minute")

**Build:**
- `Dockerfile` — Multi-stage build (builder → runtime), slim base, health check, appuser privilege drop
- `docker-compose.yml` — Services: nexus (FastAPI), nginx (reverse proxy), certbot (Let's Encrypt)
- `entrypoint.sh` — Runtime ownership fix for mounted volumes, exec to uvicorn with privilege drop

## Platform Requirements

**Development:**
- Python 3.12+
- Docker 20+ and Docker Compose
- 1GB RAM minimum (VPS constraint: tests must fit in 1GB)
- 25GB SSD minimum (DigitalOcean VPS spec)

**Production:**
- **Deployment target:** DigitalOcean VPS (1vCPU, 1GB RAM, 25GB SSD)
- **OS:** Ubuntu 22.04 LTS (inferred from VPS typical config)
- **Docker memory limits:** 800m container limit, 200m reservation (with 2GB swap)
- **Concurrency:** asyncio.Semaphore(5) hard ceiling on concurrent tasks
- **Database:** SQLite with WAL mode (concurrent reads allowed, serialized writes via asyncio.Queue)
- **Max simultaneous SQLite readers:** 3 (WAL constraint on 1GB VPS)

## Database

**Primary Storage:**
- SQLite at `/app/data/nexus_osint.db` (mounted volume in Docker)
- Tables:
  - `searches` — Search history with queries, results, timestamps, user_id
  - `token_blacklist` — Revoked JWT tokens for logout
  - `rate_limits` — IP-based rate limit tracking
  - `quota_log` — OathNet API quota usage per day

**Configuration:**
- PRAGMA journal_mode=WAL — Write-ahead logging for concurrent reads
- PRAGMA synchronous=NORMAL — Safe with WAL, 2x faster than FULL
- PRAGMA busy_timeout=5000 — Wait 5s before "database is locked" error
- PRAGMA cache_size=-8000 — 8MB in-memory cache
- PRAGMA wal_autocheckpoint=100 — Checkpoint every 100 pages

**Access Pattern:**
- Single aiosqlite.Connection (process-wide singleton in `api/db.py`)
- Writes: asyncio.Queue serialization (background writer task)
- Reads: Direct queries (WAL allows concurrent read access)
- No connection pooling (SQLite has no benefit from pooling on single machine)

## Reverse Proxy & TLS

**Nginx (Alpine):**
- Configuration: `/root/nexus-osint/nginx.conf`
- SSL/TLS:
  - Let's Encrypt via certbot auto-renewal (12h interval)
  - TLS 1.2 + 1.3, strong ciphers, HSTS 1-year max-age
  - Certificate paths: `/etc/letsencrypt/live/nexusosint.uk/`
- Rate limiting (nginx level):
  - `/api/search`: 5 req/min per IP (burst 3)
  - `/api/*`: 30 req/min per IP (burst 10)
- Static caching:
  - `/css/` and `/js/`: 1-year immutable cache headers
  - Gzip compression enabled (level 6)
- Security headers (CSP, X-Frame-Options, HSTS, Referrer-Policy, Permissions-Policy)
- Proxy to FastAPI backend: `http://nexus:8000` (internal Docker network)

## Caching

**Application-level:**
- TTLCache (cachetools) — 5-min TTL, 200-entry limit (~2MB max)
- Purpose: Reduce OathNet API quota consumption on repeat queries within 5 minutes
- Cache key: `f"{endpoint}:{query.lower().strip()}"`

**HTTP-level:**
- Nginx static asset caching (1-year immutable)
- No Redis or Memcached (single-process, in-memory cache sufficient)

---

*Stack analysis: 2026-04-19*
