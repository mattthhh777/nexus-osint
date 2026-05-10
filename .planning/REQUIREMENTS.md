# Requirements: NexusOSINT Refactoring Milestone

**Defined:** 2026-03-25
**Core Value:** A single search query returns comprehensive intelligence from 13+ OSINT modules with professional-grade data presentation — density without chaos.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### CSS Token Migration (Meridian Design System)

- [x] **CSS-01**: All 9 CSS files use Meridian semantic tokens instead of legacy tokens (--bg, --text, --amber, --line, etc.)
- [x] **CSS-02**: Zero hardcoded rgba() color values in CSS files — all replaced by token references (--color-accent-muted, --color-border-subtle, etc.)
- [x] **CSS-03**: All border-radius values constrained to design system scale: 2px (badges), 4px (buttons/inputs), 6px (cards/panels), 999px (category chips only)
- [x] **CSS-04**: All spacing values use --space-* tokens instead of arbitrary px values (14px, 18px, 36px, 56px, 68px)
- [x] **CSS-05**: All font-size values use --text-* tokens instead of hardcoded px/rem values
- [x] **CSS-06**: All font-family declarations use --font-display, --font-data, or --font-body tokens
- [x] **CSS-07**: All box-shadow values use --shadow-* tokens
- [x] **CSS-08**: All transition durations use --duration-* and --ease-* tokens
- [x] **CSS-09**: All z-index values use --z-* tokens
- [x] **CSS-10**: tokens.css contains the complete Meridian design system as single :root declaration
- [ ] **CSS-11**: Visual output is identical to pre-migration (zero visual regression)
- [x] **CSS-12**: Changing --color-accent to a different color causes ALL accent elements to update (token propagation verified)

### XSS Sanitization

- [ ] **XSS-01**: sanitizeImageUrl() function validates all URLs before insertion into src= or background-image (reject non-https, reject javascript: protocol)
- [ ] **XSS-02**: Discord avatar and banner URLs from OathNet API pass through sanitizeImageUrl() before DOM insertion
- [ ] **XSS-03**: esc() function applied to ALL template literal interpolations in render.js where API data is inserted into HTML
- [ ] **XSS-04**: grep confirms zero instances of unescaped API data in template literals across all JS files

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Security Hardening

- **SEC-01**: JWT migrated from localStorage to httpOnly cookies
- **SEC-02**: Admin HTML endpoint requires server-side auth check before serving
- **SEC-03**: OathnetClient uses singleton pattern instead of per-request instantiation

### Feature Additions

- **FEAT-01**: report_generator.py integrated into main.py with /api/report/generate endpoint
- **FEAT-02**: Cases and history persisted server-side in SQLite
- **FEAT-03**: Per-user credit system for OathNet quota management
- **FEAT-04**: Sherlock expanded from 25 to 60+ platforms

### Quality

- **QUAL-01**: pytest test suite covering auth, rate limiting, and input sanitization
- **QUAL-02**: Frontend unit tests for utils.js pure functions

## Out of Scope

| Feature | Reason |
|---------|--------|
| Next.js / React migration | Production stack works, rewrite risk too high for refactoring milestone |
| n8n integration | Never existed, not needed for current work |
| PostgreSQL / Redis | SQLite sufficient at current scale |
| Tailwind CSS / Shadcn/ui | Using custom Meridian design system |
| New OSINT modules | Feature work, not refactoring |
| Backend refactoring (split main.py) | Separate initiative, not blocking current work |
| OathNet client async migration | Works fine via asyncio.to_thread |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CSS-01 | Phase 1 | Complete |
| CSS-02 | Phase 1 | Complete |
| CSS-03 | Phase 1 | Complete |
| CSS-04 | Phase 1 | Complete |
| CSS-05 | Phase 1 | Complete |
| CSS-06 | Phase 1 | Complete |
| CSS-07 | Phase 1 | Complete |
| CSS-08 | Phase 1 | Complete |
| CSS-09 | Phase 1 | Complete |
| CSS-10 | Phase 1 | Complete |
| CSS-11 | Phase 1 | Pending |
| CSS-12 | Phase 1 | Complete |
| XSS-01 | Phase 2 | Pending |
| XSS-02 | Phase 2 | Pending |
| XSS-03 | Phase 2 | Pending |
| XSS-04 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---

# Milestone v4.2 — Database Migration (SQLite → PostgreSQL)

**Defined:** 2026-05-07
**Core Value:** Drop the asyncio.Queue write serializer; PostgreSQL MVCC handles 10-agent burst writes natively. JSONB enables sub-ms agent-payload queries that SQLite TEXT cannot index. UUID PKs kill enumeration vectors.
**Timeline:** 6-10 weeks / 8 phases
**Stack:** PostgreSQL 16-alpine + asyncpg 0.31 + SQLAlchemy 2.0 Core (schema only) + Alembic 1.13 async + psycopg2-binary 2.9 (Alembic offline only)

## Locked Decisions (2026-05-07)

| Param | Value | Rationale / Risk Re-enunciated |
|-------|-------|--------------------------------|
| UUID PKs | ALL tables (`gen_random_uuid()` from `pgcrypto`) | +30% idx size on token_blacklist/rate_limits — accepted |
| JSONB payload | yes — adds new col to `searches` in v4.2 | scope creep into v4.2 — accepted |
| Pool max_size | 10 | matches `Semaphore(10)` orchestrator ceiling |
| Pool min_size | 2 | warm pool, no cold-start surge |
| postgres `max_connections` | 20 | leaves pool headroom for Alembic + psql admin |
| postgres `shared_buffers` | 256MB | within 768MB container limit |
| postgres `work_mem` | 8MB | × ~3 sorts × 20 conns ≈ 480MB worst-case (within budget) |
| postgres `shm_size` | 256MB (Compose) | Docker default 64MB breaks hash joins |
| nexus `mem_limit` | 2500MB | TIGHT if FastAPI peaks ~800MB during 10-agent burst — Phase 23 stress test = gate; if OOM → revisit to 2700MB |
| postgres `mem_limit` | 768MB | research-resolved value |
| `quota_log` | preserve | audit value |
| `searches` | preserve | only table with historical value; ported via `asyncpg.copy_records_to_table` |
| `token_blacklist` | drop (greenfield) | ephemeral; forces re-login (already a planned event) |
| `rate_limits` | drop (greenfield) | rolling window resets harmlessly |
| Backups | `pg_dump` cron 03:00, 7d retention | restore drill on staging required |
| SQLite snapshot retention | 30 days post-cutover | rollback insurance |

## v4.2 Requirements

### Pre-Migration (Phase 17)

- [x] **DBM-01**: Audit grep returns zero unmitigated SQL dialect violations (`AUTOINCREMENT`, `INSERT OR REPLACE`, `datetime(`, `strftime(`, `rowid`, raw `?` placeholders outside the abstraction layer)
- [x] **DBM-02**: Repository abstraction layer (`db.fetch_one/fetch_all/execute/transaction`) wraps current aiosqlite implementation; all call sites refactored to use it
- [x] **DBM-03**: List of every raw SQL string in codebase produced and committed (`.planning/phases/17-*/SQL_INVENTORY.md`)
- [x] **DBM-04**: `?`→`$N` placeholder rewrite map documented per call site

### Container & Compose (Phase 19)

- [x] **DBM-05**: `docker-compose.yml` adds `postgres:16-alpine` service on private `nexus_net`, no public port mapping
- [x] **DBM-06**: Postgres `mem_limit=768MB`, `shm_size=256MB`, `command:` flags include `shared_buffers=256MB`, `work_mem=8MB`, `max_connections=20`
- [x] **DBM-07**: Named volume `postgres_data` (NOT bind mount — UID 999 permission trap)
- [x] **DBM-08**: Healthcheck + `depends_on: condition: service_healthy` gating on `nexus` service
- [x] **DBM-09**: Postgres password via Docker secret (not env var — leaks via `docker inspect`)
- [x] **DBM-10**: Nexus `mem_limit` adjusted to 2500MB; documented as Phase 23 gate

### Schema-as-Code (Phase 20)

- [x] **DBM-11**: `alembic init -t async migrations` initialized; baseline migration committed
- [x] **DBM-12**: All tables use `TIMESTAMPTZ` (zero `TIMESTAMP` without TZ — `grep -i "TIMESTAMP[^T]" migrations/` returns zero)
- [x] **DBM-13**: All boolean fields are `BOOLEAN` (zero INTEGER-as-bool)
- [x] **DBM-14**: All variable agent payloads are `JSONB` (zero JSON, zero TEXT)
- [x] **DBM-15**: All PKs are UUID via `gen_random_uuid()` with `pgcrypto` extension enabled in baseline
- [x] **DBM-16**: `searches.payload JSONB` column added with GIN index
- [x] **DBM-17**: Every FK has explicit index (Postgres does NOT auto-index FKs)
- [x] **DBM-18**: Status fields use CHECK constraints, not ENUM
- [x] **DBM-19**: `docker-compose.test.yml` provides ephemeral PG on `tmpfs` port 5433; template-database test fixtures work in CI

### Data Port (Phase 21)

- [x] **DBM-20**: `scripts/port_searches.py` uses `asyncpg.copy_records_to_table` in 1000-row batches
- [x] **DBM-21**: Type fixups applied: SQLite ISO TEXT → datetime → `TIMESTAMPTZ`; CSV `modules_run` → `TEXT[]`; INTEGER `success` → `BOOLEAN`
- [x] **DBM-22**: Row-count parity assertion passes on staging copy of production
- [x] **DBM-23**: Script is idempotent (truncate-then-load on rerun)

### Driver Swap (Phase 22)

- [x] **DBM-24**: `api/db.py` rewritten on `asyncpg.Pool` (max_size=10, min_size=2, command_timeout=30)
- [x] **DBM-25**: `_writer_loop` and `asyncio.Queue` deleted (lines 34, 46-47, 193-222 of current `api/db.py`)
- [x] **DBM-26**: Every DB call uses `async with pool.acquire() as conn:` + `async with conn.transaction():` (zero pool.acquire() outside async with)
- [x] **DBM-27**: `?` → `$N` placeholders rewritten at all call sites
- [x] **DBM-28**: All `INSERT OR REPLACE` → `INSERT ... ON CONFLICT DO UPDATE`
- [x] **DBM-29**: Every `SELECT then UPDATE` reviewed and replaced with atomic `UPDATE col = col + 1` or `SELECT FOR UPDATE` (PG READ COMMITTED ≠ SQLite SERIALIZABLE)
- [x] **DBM-30**: `idle_in_transaction_session_timeout=60s` set server-side
- [x] **DBM-31**: `/health` exposes `pool.get_idle_size()` for leak detection

### Stress Test (Phase 23) — GATE

- [x] **DBM-32**: 10 concurrent agents × N scans + `cancel_all` mid-burst loop runs to completion without OOM
- [x] **DBM-33**: `pg_stat_activity` shows zero `idle in transaction` after each cycle
- [x] **DBM-34**: `docker stats postgres` peak < 768MB
- [x] **DBM-35**: `docker stats nexus` peak < 2500MB (if exceeded → revisit `mem_limit` to 2700MB before Phase 24)
- [x] **DBM-36**: `/health` `pool.get_idle_size()` recovers between bursts
- [x] **DBM-37**: Counter consistency under concurrency verified (no lost updates)

### Cutover (Phase 24) — Irreversible

- [ ] **DBM-38**: Pre-flight artifacts captured: SQLite snapshot `nexus.db.pre-pg-YYYYMMDD`, Docker image tag `pre-pg-backup`, `git rev-parse HEAD` saved to runbook
- [ ] **DBM-39**: Read-only mode env flag flips → writes return 503 + `Retry-After`; GETs continue
- [ ] **DBM-40**: `orchestrator._registry` drained to zero (poll, max 60s)
- [ ] **DBM-41**: `port_searches.py` runs → row-count parity asserted
- [ ] **DBM-42**: `SELECT setval(pg_get_serial_sequence(...))` executed on every serial PK post-import (only applies if any sequences remain — UUID-all may eliminate)
- [ ] **DBM-43**: `DATABASE_URL` flipped to `postgresql+asyncpg://...`; `docker compose up -d --build nexus` succeeds
- [ ] **DBM-44**: Smoke test passes: `/health`, sample `/search`, `/admin`, dashboard
- [ ] **DBM-45**: Read-only mode off; SQLite file kept read-only on disk for 30 days
- [ ] **DBM-46**: Maintenance window ≤ 30 minutes; rollback playbook tested on staging beforehand

### Post-Migration (Phase 25)

- [ ] **DBM-47**: `pg_stat_statements` reviewed after 1 week production traffic; partial indexes added only on confirmed hot paths
- [ ] **DBM-48**: Per-table autovacuum tuning applied to `searches` if churn justifies (`autovacuum_vacuum_scale_factor=0.05`)
- [ ] **DBM-49**: Bloat report (`n_dead_tup / n_live_tup`) baselined
- [ ] **DBM-50**: `pg_dump` cron at 03:00 with 7-day retention active
- [ ] **DBM-51**: Restore drill on staging passes
- [ ] **DBM-52**: `aiosqlite` removed from `requirements.txt`
- [ ] **DBM-53**: CLAUDE.md updated to reflect F2 obsoletion (asyncio.Queue write serializer removed)

## Anti-Features (Explicitly Rejected)

| Feature | Reason |
|---------|--------|
| ENUM types | `ALTER TYPE ADD VALUE` is painful; use CHECK constraints |
| Stored procedures | Violates CLAUDE.md regra 3 — backend owns business logic |
| Triggers for derived data | Use generated columns instead |
| Postgres FDW to external APIs | Breaks rate limiting and observability |
| pg_cron | Couples scheduling to DB |
| Postgres-as-message-queue | Wrong tool |
| PgBouncer | No headroom on 4GB VPS; unjustified at this scale |
| ORM session (SQLAlchemy ORM) | Identity-map / lazy-load overhead; Core only for schema |
| WAL archiving / PITR | Defer to v5.0 — pg_dump RPO 24h acceptable |
| Logical replication / read replicas | Requires second host — no headroom |
| Row-level security | Only when multi-tenant SaaS |
| TimescaleDB / partitioning | Only past ~1GB `searches` table — current scale is MB |

## Open Risks Forwarded to Execution

- **R-01** (regra 5): nexus `mem_limit=2500MB` is tight; Phase 23 stress test is gate. If OOM → bump to 2700MB before Phase 24.
- **R-02**: UUID-all increases index size on greenfield-dropped tables (token_blacklist/rate_limits) — accepted; net storage minor.
- **R-03**: JSONB column added to `searches` in v4.2 expands scope; data port script must handle NULL→`'{}'::jsonb` for legacy rows.
- **R-04**: PG READ COMMITTED ≠ SQLite SERIALIZABLE — Phase 22 audit must catch every RMW pattern; missing one = lost-update bug.

## Traceability v4.2

| Requirement | Phase |
|-------------|-------|
| DBM-01 — DBM-04 | Phase 17 |
| DBM-05 — DBM-10 | Phase 19 |
| DBM-11 — DBM-19 | Phase 20 |
| DBM-20 — DBM-23 | Phase 21 |
| DBM-24 — DBM-31 | Phase 22 |
| DBM-32 — DBM-37 | Phase 23 (gate) |
| DBM-38 — DBM-46 | Phase 24 (cutover) |
| DBM-47 — DBM-53 | Phase 25 |

**Coverage:** 53 DBM requirements / 8 Postgres phases / 0 unmapped

---

# Milestone v4.2 Fold-In - Redis7 Cache Backend

**Defined:** 2026-05-08
**Core Value:** Replace per-process `cachetools.TTLCache` with shared Redis7 TTL cache so duplicate OSINT calls are avoided across restarts/workers and cache observability is no longer tied to an in-memory object.
**Scope:** Search/API response cache only. Not a queue, not a database, not session storage.
**Stack:** Redis 7 Alpine container + `redis.asyncio` Python client + fail-open in-memory fallback.

## v4.2 Redis Requirements

### Redis Cache Replacement (Phase 18)

- [x] **CACHE-01**: `docker-compose.yml` adds `redis:7-alpine` on private `internal` network with no public port mapping, `redis_data` named volume, healthcheck `redis-cli ping`, and bounded memory policy (`maxmemory=64mb`, `maxmemory-policy=allkeys-lru`).
- [x] **CACHE-02**: `.env.example` documents `REDIS_URL=redis://redis:6379/0`, `CACHE_TTL_SECONDS=300`, `CACHE_KEY_PREFIX=nexus:v1:search`, `CACHE_FAIL_OPEN=true`, and `CACHE_MAX_VALUE_BYTES=262144`.
- [x] **CACHE-03**: New `api/cache.py` exposes async cache contract: `startup()`, `shutdown()`, `get(endpoint, query)`, `set(endpoint, query, value, ttl=None)`, `stats()`, and in-memory fallback with same contract.
- [x] **CACHE-04**: `api/services/search_service.py` removes `cachetools.TTLCache` and `_api_cache`; all cache hits/sets use the async cache contract.
- [x] **CACHE-05**: Cached OathNet breach/stealer values are JSON-safe DTOs only; no `raw_response`, no live dataclass objects, no unserializable Python objects.
- [x] **CACHE-06**: Cache failures are fail-open: Redis connection/timeout/serialization errors log warning and the search continues without returning 500.
- [x] **CACHE-07**: `/health` and `/health/memory` expose cache backend, reachable status, entry estimate if available, hit/miss counters, and error counter without importing search internals.
- [x] **CACHE-08**: `requirements.txt` adds Redis Python client and removes `cachetools` after TTLCache replacement.
- [x] **CACHE-09**: Unit tests cover Redis fake/fallback behavior, TTL expiration semantics, JSON DTO round-trip for OathNet results, fail-open errors, and health stats shape.
- [x] **CACHE-10**: Integration smoke verifies Redis cache hit avoids second OathNet call for the same endpoint/query within 300 seconds.

## Traceability v4.2 Redis

| Requirement | Phase |
|-------------|-------|
| CACHE-01 - CACHE-10 | Phase 18 |

---
*v4.1 requirements defined: 2026-03-25*
*v4.2 requirements defined: 2026-05-07 — locked params per Math approval*
