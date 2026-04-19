# External Integrations

**Analysis Date:** 2026-04-19

## APIs & External Services

**Breach Databases & Breach Intelligence:**
- **OathNet** — Data breach search, stealer log lookup, domain exposure
  - SDK/Client: Custom async wrapper in `modules/oathnet_client.py`
  - Auth: `x-api-key` header (env var: `OATHNET_API_KEY`)
  - Base URL: `https://oathnet.org/api`
  - Features: Email/username breach search, stealer logs, holehe domain check, IP geolocation
  - Rate limit: 100 lookups/day (enforced per plan tier, cached at 5-min TTL to preserve quota)
  - Error handling: Graceful 429/401/403/503 responses with user-friendly messages
  - Response format: Custom dataclasses (`BreachRecord`, `StealerRecord`, `OathnetMeta`)
  - Timeout: 20 seconds per request

**Social Media & Username Enumeration:**
- **Sherlock (25+ platforms)** — Username presence across social networks
  - Implementation: Custom async HTTP checks in `modules/sherlock_wrapper.py`
  - Platforms checked (direct HTTP checks, not Sherlock subprocess):
    - GitHub, GitLab, Twitter/X, Instagram, TikTok, Reddit, LinkedIn, Pinterest, YouTube, Twitch
    - Steam, Keybase, HackerNews, Dev.to, Medium, Mastodon, Flickr, Vimeo, SoundCloud, Spotify
    - Docker Hub, npm, PyPI, Telegram, Snapchat
  - Client: httpx.AsyncClient with 10s connect timeout, 15 concurrent connections max
  - Detection method: Status code check (200) or text presence/absence in HTML
  - Fallback: Subprocess call to official `sherlock` CLI if available on PATH
  - Timeout: 10s per platform check

**OSINT Scanning (Infrastructure):**
- **SpiderFoot** — Passive reconnaissance (DNS, WHOIS, leak databases)
  - Integration: Subprocess wrapper in `modules/spiderfoot_wrapper.py`
  - Location: `/opt/spiderfoot` (Docker container path)
  - Mode: Passive (no active scanning, no direct target contact)
  - CLI invocation: `python3 sf.py -s TARGET -u passive -o json -q`
  - Timeout: 300 seconds (configurable via `SPIDERFOOT_TIMEOUT`)
  - Input validation: FQDN or bare IPv4 only (no CIDR, IPv6, URLs, path traversal)
  - Event types captured: Email, username, domain, IP, SSL certs, leaked data, darknet mentions, malicious IPs
  - Note: Requires local SpiderFoot installation; not available on Streamlit Cloud

**Frontend Asset CDNs:**
- **Google Fonts** — Web font delivery (system design: meridian.css)
  - URLs: `https://fonts.googleapis.com`, `https://fonts.gstatic.com`
  - Fonts: Inter, JetBrains Mono
  - CSP allows: `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; font-src 'self' https://fonts.gstatic.com`

## Data Storage

**Databases:**
- **SQLite** — Single-file relational database
  - Connection: aiosqlite async driver, single persistent connection (no pooling)
  - File location: `/app/data/nexus_osint.db`
  - Mode: WAL (write-ahead logging) for concurrent read access
  - Tables:
    - `searches` — User search history, queries, results payload, timestamps
    - `token_blacklist` — Revoked JWT tokens (logout tracking)
    - `rate_limits` — IP-based rate limit counters
    - `quota_log` — OathNet API quota consumption per day
  - Writer pattern: asyncio.Queue serialization (single background task writes)
  - Reader pattern: Direct queries (WAL allows concurrency)

**File Storage:**
- **Local filesystem only** — No cloud object storage (S3, etc.)
  - Data directory: `/app/data/` (Docker mounted volume `nexus_data`)
  - Users file: `/app/data/users.json` (bcrypt-hashed passwords, multi-user auth)
  - Audit database: `/app/data/audit.db` (separate from main DB for audit logging)
  - Static assets: `/app/static/` (CSS, JS, HTML served via nginx)

**Caching:**
- **In-memory TTL cache** — cachetools library
  - Purpose: OathNet response caching (5-min TTL, 200 entry limit)
  - No external cache service (Redis, Memcached)

## Authentication & Identity

**Auth Provider:**
- **Custom JWT** — Self-issued tokens, no third-party identity provider
  - Implementation: PyJWT library in `api/main.py`
  - Algorithm: HS256 (HMAC-SHA256)
  - Signing key: `JWT_SECRET` env var (validated at startup, weak defaults rejected)
  - Token expiry: 24 hours (configurable via `JWT_EXPIRE_HOURS`)
  - Storage: httpOnly cookie (secure flag set on HTTPS)
  - Revocation: Token blacklist in SQLite for logout support

**User Management:**
- Multi-user auth via JSON file (`/app/data/users.json`)
- Password hashing: bcrypt (4.2.1)
- Roles: admin, user (simple RBAC)
- Legacy fallback: Single-user auth via `APP_PASSWORD` env var (for backward compatibility)
- Max users: 50 (cap enforced, configurable via `MAX_USERS`)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, or similar)
- Logging: Python stdlib logging (loguru not in dependencies)
- Log level: WARNING (production default, can be tuned via `LOG_LEVEL`)

**Logs:**
- **Approach:** Structured logging to stdout/stderr (Docker logs)
- Categories:
  - API access: FastAPI request/response
  - Search audit: User queries logged to SQLite `searches` table
  - Rate limit events: Per-IP/per-user violations
  - OathNet quota: Daily usage tracked in `quota_log` table
  - Memory watchdog: Threshold breaches logged (Phase 10 feature)
  - Module errors: Per-agent exceptions captured (orchestrator catches all)

**Health Monitoring:**
- **Endpoint:** `GET /health`
  - Returns: JSON with memory %, CPU %, active agents, degradation mode
  - Used by: Docker healthcheck, nginx upstream monitoring
- **Memory watchdog:** Async loop monitors psutil thresholds
  - Alert: 400MB used → log warning
  - Critical: 85% memory → pause new agent tasks (graceful degradation)
- **Metrics not exposed:** No Prometheus, Datadog, or similar integration

## CI/CD & Deployment

**Hosting:**
- **DigitalOcean VPS** (1vCPU, 1GB RAM, 25GB SSD)
- IP: 146.190.142.50
- Domain: nexusosint.uk (CNAME + Let's Encrypt SSL)

**CI Pipeline:**
- None detected (no GitHub Actions, GitLab CI, Jenkins)
- Manual deployment via SCP + Docker Compose restart
- Pre-deployment: Git commit required (history preserved)
- Rollback: git revert, re-build Docker image

**Deployment Process (from CLAUDE.md):**
```bash
# 1. Commit code changes
git commit -m "..."

# 2. SCP changed files to VPS
scp -r api/ static/ nginx.conf root@146.190.142.50:/root/nexus-osint/

# 3. Rebuild and restart on VPS
ssh root@146.190.142.50 "cd /root/nexus-osint && docker compose up -d --build"
```

## Environment Configuration

**Required env vars (at runtime):**
- `OATHNET_API_KEY` — Mandatory for breach search functionality
- `JWT_SECRET` — Mandatory, validated against weak defaults at startup
- `ALLOWED_ORIGINS` — CORS origins (default: `https://nexusosint.uk`)
- `SPIDERFOOT_URL` — SpiderFoot endpoint (default: `http://spiderfoot:5001`)
- `LOG_LEVEL` — Python logging level (default: `WARNING`)
- `APP_PASSWORD` — Optional legacy fallback (recommended removed in v4.1+)
- `JWT_EXPIRE_HOURS` — Token TTL hours (default: 24)
- `MAX_USERS` — User cap (default: 50)
- `RL_*` — Rate limit tuning strings (e.g., `5/minute`)

**Optional env vars:**
- `ENV` — Deployment environment tag (default: dev, set to `prod` on VPS)
- `PYTHONPATH` — Set to `/app` in docker-compose

**Secrets location:**
- `.env` file (git-ignored, never committed)
- VPS file: `/root/nexus-osint/.env` (managed by operator, SCP'd separately)
- No secrets hardcoded in code (enforced by linting rules in CLAUDE.md)

## Webhooks & Callbacks

**Incoming:**
- None detected (no webhook receivers defined)
- Search is pull-based (client initiates via `/api/search` POST)

**Outgoing:**
- None detected (no external webhooks fired)
- No event streaming to third parties
- SSE (Server-Sent Events) for search progress is browser push only (not external webhook)

## Rate Limiting

**Inbound (nginx + slowapi):**
- Global: `/api/` → 30 req/min per IP (burst 10)
- Search-specific: `/api/search` → 5 req/min per IP (burst 3)
- Login: `RL_LOGIN_LIMIT` → 5/minute per IP (slowapi)
- Register: `RL_REGISTER_LIMIT` → 3/hour per IP
- SpiderFoot scan: `RL_SPIDERFOOT_LIMIT` → 3/hour per user
- Admin: `RL_ADMIN_LIMIT` → 30/minute per user
- Read endpoints: `RL_READ_LIMIT` → 60/minute per user

**Outbound (agents → external APIs):**
- **OathNet:** 100 lookups/day (built into API plan tier)
  - Caching: 5-min TTL reduces quota pressure
  - Enforcement: API returns 429 on quota exhausted
- **Sherlock HTTP checks:** Per-platform connect timeout 10s, 15 concurrent max (httpx connection pool)
- **SpiderFoot:** Single scan timeout 300s, shared resource (no concurrent scans in current design)

## Reverse Proxy Configuration

**Nginx (Alpine image):**
- Configuration file: `nginx.conf` at repo root, mounted to `/etc/nginx/nginx.conf:ro` in container
- HTTP/2 enabled on port 443 (TLS)
- HTTPS only (port 80 redirects to 443, ACME challenge handled)
- Certificate auto-renewal: certbot service (12h interval)
- Static asset serving: `/css/` and `/js/` with long-lived cache headers
- Proxy buffering: Disabled for SSE `/api/search` streaming
- Request timeout: 600s for `/api/search` (SSE long-poll), 60s for general `/api/`

---

*Integration audit: 2026-04-19*
