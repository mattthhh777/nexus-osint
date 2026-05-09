# Project Research Summary — NexusOSINT v4.2

**Project:** NexusOSINT — OSINT scanning platform (FastAPI + Vanilla JS, single-tenant, internal/commercial)
**Domain:** Database migration — SQLite (aiosqlite + WAL + asyncio.Queue) → PostgreSQL 16 (asyncpg + pool)
**Researched:** 2026-05-07
**Confidence:** HIGH (driver/version/patterns well-documented; quantitative RAM estimates MEDIUM, environment-dependent)

---

## Executive Summary

NexusOSINT's v4.1 SQLite + single-writer-queue (F2) is correct for SQLite but is now the binding constraint: bursty 10-agent writes serialize behind one writer, JSON columns are opaque to indexes (`LIKE '%x%'` full scans), and there is no schema migration tooling. The research consensus is unambiguous: migrate to **PostgreSQL 16-alpine + asyncpg + Alembic async**, drop the write queue entirely, use **JSONB** for variable agent payloads, and use **TIMESTAMPTZ + UUID + BOOLEAN** as the canonical types. Postgres MVCC replaces the queue at the engine level — the architectural simplification is the migration's biggest win, not raw latency.

The migration is feasible on the existing 4GB Hetzner VPS, but the RAM envelope is tight and non-negotiable: Postgres must be capped to ~700-768MB (container `mem_limit`), with `shared_buffers=256MB`, `work_mem=8MB`, and `max_connections` between 20-30. The asyncpg pool is sized to match `Semaphore(10)` — `max_size=10-12`, `min_size=2`. There is no headroom for PgBouncer (and it's unjustified at this scale), no headroom for a hot standby, and no room for sloppy defaults like Postgres's `max_connections=100` which would OOM-kill the host.

The dominant risks are not technical surprises but **discipline failures**: SQL dialect drift (`AUTOINCREMENT`, `INSERT OR REPLACE`, `?` placeholders), silent type corruption (`TIMESTAMP` instead of `TIMESTAMPTZ`), TaskGroup-cancellation pool leaks, and a botched cutover that loses in-flight scan writes. Mitigated by: an audit-first phase before any code change, a thin DB abstraction layer before driver swap, a tested cutover script with read-only mode and sequence reset, and a 14-30 day SQLite cold-backup retention. Recommended timeline: **6-8 weeks across 8 phases**, with a planned ~30-minute maintenance window for cutover.

---

## Key Findings

### Recommended Stack

PostgreSQL 16-alpine on the existing VPS (no separate DB host), driven by **asyncpg 0.31.0** (native async, ~5× faster than psycopg3, no libpq dependency), schema managed by **Alembic 1.13+ in async mode**, and queries written as **raw asyncpg with SQLAlchemy 2.0 Core for schema-as-code only** (no ORM session — Core gives Alembic autogenerate without paying for identity-map / lazy-load overhead). Backups via **`pg_dump` cron from inside the container** with 7-day retention.

**Core technologies:**
- **PostgreSQL 16-alpine** (16.x latest minor) — relational engine; v16 is mature with bug fixes consolidated, alpine reduces image ~60% vs debian-slim. Defer v17 to v5.0.
- **asyncpg 0.31.0** — async-native driver, supports Postgres 9.5–18 / Python 3.9–3.14; built-in connection pool sufficient for single-app deployment.
- **SQLAlchemy 2.0 Core** (no ORM) — `MetaData`/`Table` definitions feed Alembic autogenerate; runtime queries stay on raw asyncpg.
- **Alembic 1.13+ (async template)** — versioned schema migrations; **schema only** — data migration is a separate one-shot Python script.
- **psycopg2-binary 2.9** — Alembic offline mode only (Alembic offline is sync); never in runtime.

Detail: see `STACK.md`.

### Expected PostgreSQL Features Adoption

The features research is opinionated per NexusOSINT's exact workload (bursty agent writes + dashboard reads + JSON-shaped agent results). Verdicts:

**Must have (P1 — adopt during migration):**
- **JSONB + GIN index** for `results.payload` — replaces opaque `extra_fields TEXT`; enables `payload @> '{"sites_found":["github"]}'` in sub-millisecond on 100k rows. **This is the single biggest product-level win.**
- **Native UUID PKs** (`gen_random_uuid()` from `pgcrypto`) — kills `/api/scan/1,2,3` enumeration vector; distributed-safe; no sequence contention.
- **Drop the asyncio.Queue write serializer** — Postgres MVCC handles concurrency; estimated **~10-15× improvement on burst write tail latency** for 10 simultaneous agents.
- **CHECK constraints, not ENUM**, for status fields — schema flexibility for active iteration; ENUM `ALTER TYPE ADD VALUE` is painful, removal is essentially impossible.
- **TIMESTAMPTZ everywhere** — never `TIMESTAMP`; explicit UTC storage; kills DST/locale corruption.
- **Tuned `postgresql.conf`** for 4GB VPS coexisting with FastAPI (see Confidence section for resolved values — minor cross-file disagreement noted).

**Should have (P2 — within 30 days of migration / v4.3):**
- **tsvector + GIN for cross-scan FTS** with `'simple'` config (not `english`/`portuguese` — stemming corrupts OSINT identifiers like usernames). Fills a known dashboard gap (grep-across-history).
- **LISTEN/NOTIFY for SSE dashboard updates** — eliminates ~144k pointless poll reads/day at 10 active users.
- **Partial indexes on hot paths** (e.g., `WHERE status IN ('queued','running')`) — but profile-first via `pg_stat_statements`; do not pre-optimize.

**Defer (v5.0+):**
- WAL archiving / PITR (current pg_dump RPO of 24h acceptable for OSINT internal use).
- Logical replication / read replicas (requires a second host — no headroom on 4GB VPS, no current need).
- Row-level security (only when multi-tenant SaaS).
- TimescaleDB / partitioning (only past ~1GB `searches` table — current scale is ~MB).

**Anti-features explicitly rejected:** ENUM types, stored procedures (violates CLAUDE.md regra 3 — backend owns business logic), triggers for derived data (use generated columns), Postgres FDW to external APIs (breaks rate limiting/observability), pg_cron (couples scheduling to DB), Postgres-as-message-queue.

Detail: see `FEATURES.md`.

### Architecture Approach

The target architecture is a **two-container Compose** (postgres + nexus on a private bridge network), with the FastAPI app talking to Postgres via TCP and an asyncpg connection pool sized to match the existing `Semaphore(10)` orchestrator ceiling. The entire `_writer_loop` / `asyncio.Queue` machinery in `api/db.py` (lines 34, 46-47, 193-222) is **deleted**; the public `db.write` / `db.write_await` / `db.read_*` API surface is preserved so call sites change minimally (only SQL placeholder syntax `?` → `$1`).

**Migration strategy is greenfield + selective preserve:** drop `token_blacklist` (ephemeral by definition — forces re-login, already a planned event), drop `rate_limits` (rolling window, resets harmlessly), drop `quota_log` (nice-to-have); **preserve only `searches`** (audit log — the only table with historical value). Data port via a one-shot `scripts/port_searches.py` using `asyncpg.copy_records_to_table` in 1000-row batches (10-50× faster than INSERT loop, bypasses per-row WAL overhead). Type fixups during port: SQLite ISO TEXT → `TIMESTAMPTZ`, CSV `modules_run` → `TEXT[]`, `INTEGER` flags → `BOOLEAN`.

**Major components:**
1. **`postgres` container** — `postgres:16-alpine`, named volume `postgres_data` (NOT bind mount — UID 999 permission trap), no host port mapping (only reachable via `nexus_net`), password via Docker secret (not env var — leaks via `docker inspect`).
2. **`api/db.py` (rewritten)** — owns `asyncpg.Pool`, exposes same public methods; internal queue/writer-task gone.
3. **`api/migrations/`** (new) — Alembic async environment + versioned migrations; baseline is the greenfield schema.
4. **`scripts/port_searches.py`** (new, one-shot) — SQLite → PG data port for `searches` only, with row-count parity assertion.
5. **`tests/conftest.py`** (rewritten) — template-database cloning (`CREATE DATABASE ... TEMPLATE`) for per-test isolation at ~50ms cost; `docker-compose.test.yml` provides ephemeral PG on `tmpfs` for CI.

Detail: see `ARCHITECTURE.md`.

### Critical Pitfalls (Top 5)

Twelve pitfalls documented; the five with highest combined likelihood × impact:

1. **SQL dialect drift** (`AUTOINCREMENT`, `INSERT OR REPLACE`, `datetime()`, `strftime()`, `rowid`, `?` placeholders, `||` NULL semantics). Mitigation: mandatory pre-flight `grep -rE` audit; rewrite `INSERT OR REPLACE` → `INSERT ... ON CONFLICT DO UPDATE`; integration test suite must run against real Postgres testcontainer, not just `:memory:` SQLite.

2. **Type mapping landmines** — `TIMESTAMP` (no TZ) silently corrupts on container TZ change; `INTEGER` for booleans is rejected by asyncpg (`invalid input for query argument: 1 (a boolean is required, not int)`); JSON-as-TEXT cannot be indexed. Mitigation: `TIMESTAMPTZ` everywhere (zero `TIMESTAMP` in migrations), explicit `BOOLEAN`, `JSONB` not `JSON` not `TEXT`, `BIGINT GENERATED ALWAYS AS IDENTITY` or `UUID` for PKs.

3. **TaskGroup-cancellation pool leaks** — `pool.acquire()` outside an `async with` block leaks connections to `IDLE IN TRANSACTION` on cancellation, exhausting the pool within minutes under cancel storms. Mitigation: every DB call uses `async with pool.acquire() as conn:` + `async with conn.transaction():`; set `command_timeout=30` on pool and `idle_in_transaction_session_timeout=60s` server-side; `/health` exposes `pool.get_idle_size()` for leak detection.

4. **Postgres OOM on 4GB VPS** — defaults assume dedicated ≥8GB host; default `max_connections=100 × work_mem=4MB × 2-3 sorts ≈ 800MB-1.2GB peak`, on top of FastAPI ~500MB and OS, will OOM-kill. Mitigation: explicit `max_connections=20-30`, `shared_buffers=256MB`, `work_mem=8MB`, container `mem_limit=700-768MB`, `shm_size: 256mb` (Docker default 64MB breaks hash joins).

5. **Cutover data loss** — naive "stop, dump, restore, start" loses writes from in-flight scans and clients retrying through nginx; sequence collisions (`duplicate key value`) on first INSERT because Postgres sequences start at 1 while imported data has higher IDs; SQLite VACUUM never run blows the maintenance window. Mitigation: scheduled maintenance window (per CLAUDE.md regra), read-only mode env flag, drain `orchestrator._registry` to zero (≤60s), tested port script with row-count parity assertion, `SELECT setval(pg_get_serial_sequence(...))` post-import on every serial PK, SQLite snapshot retained 30 days.

Honorable mentions: isolation-level race conditions (SQLite SERIALIZABLE → PG READ COMMITTED — `SELECT then UPDATE` becomes a lost-update bug; fix with atomic `UPDATE col = col + 1` or `SELECT FOR UPDATE`), Compose startup race (`depends_on: condition: service_healthy`), volume permissions (UID 999 — same class as the prior `static/` 700-perm incident), `pg_dump` version mismatch (always `docker exec` inside container).

Detail: see `PITFALLS.md`.

---

## Implications for Roadmap

Suggested 8-phase structure for v4.2 — designed so each phase is independently shippable to staging, and the irreversible cutover is preceded by maximum verification.

### Phase 1 — Pre-Migration Audit & DB Abstraction Layer
**Rationale:** All four research files agree the dominant risk is **discipline**, not technology. Audit first, then build a thin repository layer so the driver swap in Phase 5 is contained to one module.
**Delivers:** `grep -rE "AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(|rowid|fetchone\(|fetchall\("` audit report; list of every raw SQL string; `?`→`$1` placeholder map; thin `db.fetch_one/fetch_all/execute/transaction` repository layer wrapping aiosqlite (still on SQLite at end of phase).
**Avoids:** PITFALLS Pitfall 1 (dialect drift), Pitfall 4 (asyncpg API differs), sed-replace disaster.

### Phase 2 — Postgres Container + Compose Wiring (parallel deploy)
**Rationale:** Stand up Postgres alongside SQLite without cutover risk. App still on SQLite.
**Delivers:** `docker-compose.yml` with `postgres:16-alpine`, named volume `postgres_data`, healthcheck, `condition: service_healthy` gating, password as Docker secret, `mem_limit=768MB`, `shm_size: 256mb`, tuned `command:` flags (resolved values below), no public port mapping.
**Avoids:** Pitfalls 7 (OOM), 8 (startup race), 9 (volume permissions — named volume, not bind), Anti-Pattern 4 (public Postgres).

### Phase 3 — Schema-as-Code + Alembic Async + Test Infra
**Rationale:** Schema must be defined and reviewed before any data touches it. Test infra must work on real PG before code is written against PG.
**Delivers:** `alembic init -t async migrations`, baseline migration with `MetaData`/`Table` for all tables (greenfield schema using TIMESTAMPTZ / BOOLEAN / JSONB / UUID / `BIGINT GENERATED ALWAYS AS IDENTITY` / `TEXT[]`), per-table indexes including FK indexes (Postgres does NOT auto-index FKs), template-database test fixtures, `docker-compose.test.yml` with tmpfs PG on port 5433.
**Avoids:** Pitfall 2 (type mapping), Performance Trap "Missing indexes on FKs".
**Verification:** `\d+ table_name` confirms TIMESTAMPTZ; `grep -i "TIMESTAMP[^T]" migrations/` returns zero; FK index cross-check passes.

### Phase 4 — Data Port Script (`searches` only)
**Rationale:** Greenfield + selective preserve dramatically reduces migration scope. `searches` is the only table with historical value.
**Delivers:** `scripts/port_searches.py` using `asyncpg.copy_records_to_table` in 1000-row batches; type fixups (ISO TEXT → datetime → TIMESTAMPTZ; CSV `modules_run` → `TEXT[]`; INTEGER `success` → BOOLEAN); row-count parity assertion; idempotent (truncate-then-load on rerun); timed on staging copy of production.
**Avoids:** Pitfall 11 (cutover data loss — script tested before maintenance window).

### Phase 5 — Repository Layer Switch + Code Audit Pass 2
**Rationale:** With Phase 1 abstraction in place, swap the implementation behind it. Audit isolation-level race conditions specifically (SQLite SERIALIZABLE → PG READ COMMITTED).
**Delivers:** `api/db.py` rewritten on asyncpg pool; `_writer_loop` and `asyncio.Queue` deleted (lines 34, 46-47, 193-222); `?` → `$N` placeholders rewritten at ~30-50 call sites; `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE` rewrites; every `SELECT then UPDATE` reviewed and replaced with atomic `UPDATE col = col + 1` or `SELECT FOR UPDATE`; pool always inside `async with`; `command_timeout=30`, `idle_in_transaction_session_timeout=60s`.
**Avoids:** Pitfall 5 (cancellation leaks), Pitfall 6 (RMW races), Anti-Pattern 1 (re-implementing the queue).

### Phase 6 — Concurrency & Memory Stress Test
**Rationale:** Don't ship the cutover until the new architecture is verified under load matching production burst patterns.
**Delivers:** Test scenario: 10 concurrent agents × N scans, `cancel_all` mid-burst, repeated; `pg_stat_activity` clean (zero `idle in transaction`) after each cycle; `docker stats` postgres < 768MB peak; `docker stats` nexus < 800MB peak; `/health` reports `pool.get_idle_size()` recovering; counters consistent under concurrency; slow-query log reviewed.
**Avoids:** Discovering OOM or pool leaks in production.

### Phase 7 — Cutover (maintenance window, ~30 min)
**Rationale:** Irreversible step. Execute the documented playbook exactly.
**Delivers:**
1. Pre-flight: SQLite snapshot (`cp nexus.db nexus.db.pre-pg-$(date +%Y%m%d)`), Docker image tagged `pre-pg-backup`, `git rev-parse HEAD` saved.
2. Read-only mode flag flipped → 503 + `Retry-After` for writes; GETs continue.
3. Drain `orchestrator._registry` to zero (poll, max 60s).
4. Run `port_searches.py` → assert row-count parity → run `SELECT setval(pg_get_serial_sequence('searches','id'), MAX(id))`.
5. Flip `DATABASE_URL` env to `postgresql+asyncpg://...` → `docker compose up -d --build nexus`.
6. Smoke test: `/health`, sample `/search`, `/admin`, dashboard.
7. Read-only mode off; announce restored.
8. SQLite file kept read-only on disk for 30 days.
**Avoids:** Sequence collisions, lost in-flight writes, no rollback path.

### Phase 8 — Post-Migration Tuning + Backup Hardening (1-week observation)
**Rationale:** Tuning needs real production traffic data; defer optimization until measured.
**Delivers:** `pg_stat_statements` review → partial indexes on confirmed hot paths only; per-table autovacuum tuning for `searches` if churn justifies (`autovacuum_vacuum_scale_factor=0.05`); bloat report (`n_dead_tup / n_live_tup`); `pg_dump` cron at 03:00 with 7-day retention; restore drill on staging; `aiosqlite` removed from `requirements.txt`; CLAUDE.md updated to reflect F2 obsoletion.
**Avoids:** Pre-optimizing without data; backup-you-have-not-restored anti-pattern (Pitfall 10, Pitfall 12).

### Phase Ordering Rationale

- **Audit before abstraction before swap** — every research file warns sed-replace is the disaster path.
- **Postgres up before schema before code** — can't write Alembic migrations against a non-existent server; can't write code against a non-existent schema.
- **Tests on real PG before stress before cutover** — SQLite `:memory:` cannot validate dialect/concurrency assumptions.
- **Stress before cutover** — production traffic is not the place to discover pool leaks.
- **Tuning after observation** — both STACK and FEATURES emphasize "profile-first, don't pre-optimize".
- **Greenfield + selective preserve** simplifies Phase 4 (one table, not four) and Phase 7 (no token/rate-limit replay).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Schema-as-Code):** UUIDv7 vs UUIDv4 trade-off (B-tree locality on history pagination — irrelevant at NexusOSINT scale per FEATURES, but worth a 30-min decision); whether to use SQLAlchemy 2.0 `MetaData/Table` vs handwritten Alembic SQL.
- **Phase 5 (Code Audit Pass 2):** Concrete enumeration of every `SELECT-then-UPDATE` site is project-specific and cannot be researched generically.
- **Phase 7 (Cutover):** Maintenance-window comms plan is product-decision Math owns, not a research question.

Phases with standard, well-documented patterns (skip research-phase):
- Phase 1 (Audit + Abstraction), Phase 2 (Compose wiring), Phase 4 (Data port), Phase 6 (Stress test), Phase 8 (Tuning).

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | asyncpg 0.31.0 verified on PyPI/GitHub; Postgres 16-alpine official; SQLAlchemy 2.0 + Alembic async pattern is mainstream FastAPI ecosystem. |
| Features | HIGH | All from official PG 16 docs (JSONB, FTS, NOTIFY, generated columns, RLS, replication chapters); verdicts are opinionated against NexusOSINT's exact workload. |
| Architecture | HIGH | Patterns verified against asyncpg/SQLAlchemy/Postgres official docs; component diff verified against current `api/db.py:34-222`. |
| Pitfalls | HIGH | Well-documented failure modes from asyncpg/PG 16/SQLAlchemy 2 docs + community wiki; reuses lessons from prior NexusOSINT incidents. |

**Overall confidence:** HIGH on direction, recommendations, and ordering. MEDIUM on specific quantitative tuning numbers (RAM per connection varies with `work_mem` and query complexity).

### Cross-File Conflicts Resolved

The four research files agree on direction but disagree on **specific tuning numbers**. Resolutions to lock in before Phase 2:

| Parameter | STACK | FEATURES | ARCH | PITFALLS | **Resolved** | Rationale |
|---|---|---|---|---|---|---|
| `shared_buffers` | 256MB | 768MB | 256MB | 256MB | **256MB** | 3-of-4 agree; FEATURES assumed PG had ~1.3GB but coexisting with FastAPI peak (~800MB) tightens this. |
| `effective_cache_size` | 512MB | 1.5GB | 768MB | 1GB | **768MB** | ARCHITECTURE's number is the median and matches realistic OS-cache leftover. Hint only — no allocation. |
| `work_mem` | 8MB | 16MB | 8MB | 8MB | **8MB** | 3-of-4 agree; with 12 connections × 2 sorts, 8MB → 192MB worst case is already significant. |
| `max_connections` | 30 | 25 | 30 | 20 | **25** | Compromise: pool max 12 + Alembic + pgcli + pg_dump + headroom. PITFALLS (20) too tight if backup runs during light load. |
| Pool `max_size` | 10 | 12 | 12 | 10 | **12** | Match `Semaphore(10)` agents + 2 endpoint slots. STACK's 10 too tight if a long-running endpoint coincides with a 10-agent burst. |
| Postgres `mem_limit` | 700MB | ~1GB | 768MB | 1GB | **768MB** | ARCHITECTURE/PITFALLS upper bound; STACK's 700MB risks throttling under maintenance ops. Leaves ~2.7GB for FastAPI + OS. |
| `nexus` `mem_limit` | 2800MB | — | 2500MB | — | **2500MB** | ARCHITECTURE's number; reduced from current 3500MB to make room for 768MB Postgres. |
| Backup strategy | pg_dump cron 7d | pg_basebackup + WAL archiving | (defers) | pg_dump from container | **pg_dump from container, cron 7d** | FEATURES' WAL archiving needs external storage and is over-engineered for current scale. STACK + PITFALLS agree pg_dump suffices until SLA/data volume justifies WAL-G. Revisit in v5.0. |

These resolutions are opinionated. Document them in the roadmap so they don't get re-litigated phase by phase.

### Gaps to Address During Planning/Execution

- **RAM per asyncpg connection on Postgres 16-alpine** — research estimates ~8-12MB; verify empirically in Phase 6 stress test before declaring `max_size=12` safe. If actual is >15MB, drop to `max_size=10`.
- **`port_searches.py` runtime on production-sized `searches` table** — research estimates COPY at 10-50× INSERT; actual depends on row count and width. Time on staging copy of production before scheduling the maintenance window.
- **Read-only mode implementation** — not researched; needs design decision (env flag vs feature flag vs middleware). Suggested: middleware that 503s POST/PUT/PATCH/DELETE when `os.getenv('READ_ONLY')=='1'`.
- **Sequence reset for non-`searches` tables** — greenfield strategy means no reset needed for `token_blacklist`/`rate_limits`/`quota_log`, but if any table is added to the preserve list during Phase 3, the cutover script must reset its sequence.
- **Whether to use a non-superuser app role (`nexus_app` with table-level GRANTs only)** — PITFALLS Security Mistakes recommends this; STACK/ARCHITECTURE imply but don't specify. Defer to v4.3 hardening or include in Phase 8 — Math's call.
- **Maintenance window scheduling and user comms** — product/operational decision, not technical.

### Timeline Estimate

**6-8 weeks across 8 phases**, assuming Math operates in vibe-coding cadence with Opus-plan / Sonnet-execute alternation per CLAUDE.md:

| Phase | Estimate | Notes |
|---|---|---|
| 1 — Audit + Abstraction | 1 week | Mostly audit + repository layer; small but careful. |
| 2 — Compose wiring | 2-3 days | Mechanical once tuning numbers locked. |
| 3 — Schema + Alembic + Test infra | 1 week | First time setup; Alembic async has gotchas. |
| 4 — Port script | 3-5 days | Including staging timing run. |
| 5 — Repository switch + audit pass 2 | 1-2 weeks | Touch every call site; concurrency audit. |
| 6 — Stress test | 3-5 days | Includes fixing whatever it surfaces. |
| 7 — Cutover | 1 day prep + ~30 min window | High focus, low coding. |
| 8 — Post-migration tuning | 1 week observation + 2-3 days work | Spread across the week. |

Critical path is Phase 5 (~50 SQL call sites + concurrency audit). Phase 1 can compress if SQL inventory is small.

---

## Sources

### Primary (HIGH confidence)
- PostgreSQL 16 official docs (postgresql.org/docs/16/) — JSONB, FTS, NOTIFY, generated columns, RLS, replication, runtime-config-resource
- asyncpg PyPI 0.31.0 + GitHub releases — driver version, Python/PG compatibility
- asyncpg API docs — `create_pool`, `copy_records_to_table`, cursor patterns, FAQ
- GitHub asyncpg #339 — PgBouncer + `statement_cache_size=0` requirement
- SQLAlchemy 2.0 async docs
- Alembic async cookbook
- Docker compose `depends_on` conditions docs
- PostgreSQL Docker Hub — image tags, healthcheck conventions
- Instaclustr — Postgres Docker shared memory / `shm_size` 64MB issue
- PostgreSQL Continuous Archiving docs — WAL spec
- CLAUDE.md (in-repo) — hardware budget, exception rules, deploy process, regra 3
- `api/db.py:34-222` (in-repo) — current writer-loop being deleted; Pitfall 9 ties to prior `static/` 700-perm incident in `project_deployment_vps.md` memory

### Secondary (MEDIUM confidence)
- PostgreSQL Tuning Wiki — shared_buffers/work_mem ratios
- pgtune.leopard.in.ua — small-VPS tuning baseline (≤4GB profile)
- PostgreSQL "Don't Do This" community wiki
- SISL — pg_dump vs WAL-G comparison
- TestDriven.io — FastAPI + Async SQLAlchemy + Alembic
- Berk Karaal — FastAPI async SA2 Alembic Postgres Docker recipe
- TigerData — psycopg2 vs psycopg3 benchmark
- fernandoarteaga.dev — Psycopg3 vs Asyncpg

### Tertiary (LOW confidence — needs validation in Phase 6)
- Quantitative claim "~10-15× improvement on burst write tail latency" (FEATURES) — derived from queueing-theory back-of-envelope, not measured on NexusOSINT workload. Validate in Phase 6 stress test before citing externally.
- Per-connection asyncpg backend RAM (~8-12MB) — varies with `work_mem` and query patterns; treat as planning estimate, verify empirically.
