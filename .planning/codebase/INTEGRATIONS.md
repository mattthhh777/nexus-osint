# External Integrations

**Analysis Date:** 2026-03-25

## APIs & External Services

**OSINT Data (Primary):**
- OathNet API — breach records, stealer logs, holehe (email-to-service), IP info, Discord lookup, Xbox, Steam, Roblox, subdomain enumeration, GHunt (Google OSINT), Minecraft history, victims (compromised machines), Discord→Roblox pivot
  - SDK/Client: `modules/oathnet_client.py` (custom wrapper, `requests.Session`)
  - Base URL: `https://oathnet.org/api`
  - Auth: `x-api-key` header
  - Env var: `OATHNET_API_KEY`
  - Endpoints used:
    - `POST /service/search/init` — session management
    - `GET /service/search-breach` — breach database search
    - `GET /service/v2/stealer/search` — stealer log search
    - `GET /service/holehe` — email-to-registered-services check
    - `GET /service/ip-info` — IP geolocation
    - `GET /service/steam` — Steam profile
    - `GET /service/xbox` — Xbox profile
    - `GET /service/roblox-userinfo` — Roblox profile
    - `GET /service/discord-userinfo` — Discord profile
    - `GET /service/discord-username-history` — Discord username history
    - `GET /service/discord-to-roblox` — Discord ID → Roblox account
    - `GET /service/extract-subdomain` — subdomain enumeration
    - `GET /service/ghunt` — Google account OSINT
    - `GET /service/mc-history` — Minecraft username history
    - `GET /service/v2/victims/search` — compromised machine profiles
    - `GET /service/v2/victims/{log_id}` — victim log manifest
    - `GET /service/v2/victims/{log_id}/files/{file_id}` — victim log file content

**Social Platform Checks (Internal Sherlock Engine):**
- 25 platforms checked directly via async HTTP (no API keys required)
- Implemented in `modules/sherlock_wrapper.py` using `aiohttp`
- Platforms: GitHub, GitLab, Twitter/X, Instagram, TikTok, Reddit, LinkedIn, Pinterest, YouTube, Twitch, Steam, Keybase, HackerNews, Dev.to, Medium, Mastodon, Flickr, Vimeo, SoundCloud, Spotify, DockerHub, NPM, PyPI, Telegram, Snapchat
- Falls back to Sherlock CLI subprocess if installed on PATH and finds results

**OSINT Automation (Optional, External):**
- SpiderFoot — 200+ OSINT module scanner
  - Integration: REST API calls via `httpx` to SpiderFoot's own HTTP server
  - Config: `SPIDERFOOT_URL` env var (default `http://spiderfoot:5001`)
  - Endpoints: `/api/v1/ping`, `/api/v1/startscan`, `/api/v1/scanstatus/{id}`, `/api/v1/scaneventresults/{id}`
  - Status: NOT included in `docker-compose.yml` — must be deployed separately
  - Also has a legacy CLI subprocess wrapper in `modules/spiderfoot_wrapper.py` (unused in FastAPI path, contains Streamlit render code indicating prior stack migration)

**Font CDN:**
- Google Fonts — `Space Grotesk` and `JetBrains Mono` loaded in `static/index.html`
  - No API key; referenced in nginx CSP: `https://fonts.googleapis.com`, `https://fonts.gstatic.com`

## Data Storage

**Databases:**
- SQLite via `aiosqlite`
  - File: `/app/data/audit.db` (in persistent Docker volume `nexus_data`)
  - Tables:
    - `searches` — full audit log of every search (user, IP, query, query type, module list, counts, elapsed time)
    - `rate_limits` — persistent per-IP rate limiting that survives container restarts
    - `quota_log` — OathNet API quota snapshots (last 100 entries)

**User Store:**
- JSON flat file: `/app/data/users.json` (in persistent Docker volume `nexus_data`)
- Schema: `{ username: { password_hash, role, created_at, active } }`
- Passwords: bcrypt hash of SHA-256 of password (double-hashing to avoid bcrypt 72-byte limit)

**File Storage:**
- Local Docker volume only (`nexus_data` at `/app/data`)
- No cloud object storage

**Caching:**
- None — no Redis, Memcached, or in-process cache

## Authentication & Identity

**Auth Provider:**
- Custom — no third-party auth provider
  - JWT (HS256) issued by `/api/login`, validated on every protected route via `HTTPBearer` dependency
  - Token expiry: 24 hours (configurable via `JWT_EXPIRE_HOURS`)
  - Secret: `JWT_SECRET` env var; falls back to ephemeral derived secret (unsafe for production restarts)
  - Multi-user: `users.json` flat file
  - Legacy: single `APP_PASSWORD` env var creates `admin` user on first boot
  - Admin role: checked via `get_admin_user` dependency for `/api/admin/*` routes
  - Frontend: stores token in `localStorage` as `nx_token`, sends as `Authorization: Bearer` header

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Datadog, or equivalent

**Logs:**
- Python `logging` module, level controlled by `LOG_LEVEL` env var (default `WARNING`)
- Logger name: `nexusosint`
- No structured logging or log shipping configured

## CI/CD & Deployment

**Hosting:**
- VPS/self-hosted (implied by `docker-compose.yml` with Certbot and nginx on bare ports 80/443)
- Domain: `nexusosint.uk`

**CI Pipeline:**
- None detected — no `.github/`, no CI config files

## Environment Configuration

**Required env vars:**
- `OATHNET_API_KEY` — OathNet API authentication (required, enforced in `docker-compose.yml` with `?:`)
- `JWT_SECRET` — JWT signing secret (required for production stability)

**Optional env vars:**
- `APP_PASSWORD` — Legacy single-user password
- `ALLOWED_ORIGINS` — Comma-separated CORS origins (default: `https://nexusosint.uk`)
- `LOG_LEVEL` — Python log level (default: `WARNING`)
- `JWT_EXPIRE_HOURS` — Token lifetime in hours (default: `24`)
- `SPIDERFOOT_URL` — SpiderFoot server URL (default: `http://spiderfoot:5001`)
- `SPIDERFOOT_PATH` — SpiderFoot CLI install path (default: `/opt/spiderfoot`)
- `SPIDERFOOT_TIMEOUT` — SpiderFoot scan timeout in seconds (default: `300`)

**Secrets location:**
- `.env` file in project root (not committed; loaded by `python-dotenv`)

## Webhooks & Callbacks

**Incoming:**
- None — no webhook receivers

**Outgoing:**
- None — all external calls are request-initiated (user triggers search)

---

*Integration audit: 2026-03-25*
