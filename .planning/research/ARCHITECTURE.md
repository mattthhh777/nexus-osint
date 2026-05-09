# Architecture Patterns

**Domain:** SQLite → PostgreSQL migration for NexusOSINT (FastAPI + asyncio + Docker on Hetzner 4GB VPS)
**Researched:** 2026-05-07
**Confidence:** HIGH (asyncpg/SQLAlchemy/Postgres patterns verified against official docs and CLAUDE.md constraints)

---

## Current vs Target Architecture

### Current (SQLite — single-writer queue)

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI workers=1 (asyncio event loop)                     │
│                                                             │
│   ┌──────────┐    ┌──────────┐   ...  ┌──────────┐          │
│   │ Endpoint │    │ Agent #1 │        │ Agent #N │          │
│   └────┬─────┘    └────┬─────┘        └────┬─────┘          │
│        │ write          │ write             │ write         │
│        ▼                ▼                   ▼               │
│   ┌──────────────────────────────────────────────┐          │
│   │  asyncio.Queue (maxsize=1000)                │          │
│   └──────────────────┬───────────────────────────┘          │
│                      ▼                                      │
│   ┌──────────────────────────────────────────────┐          │
│   │  _writer_loop (single task)                  │          │
│   └──────────────────┬───────────────────────────┘          │
│                      │                                      │
│   reads (WAL, direct)│        writes (serialized)           │
│        ┌─────────────┴─────────────┐                        │
│        ▼                                                    │
│   ┌──────────────────────────────────────────────┐          │
│   │  aiosqlite single Connection                 │          │
│   │  PRAGMA journal_mode=WAL, busy_timeout=5000  │          │
│   └──────────────────┬───────────────────────────┘          │
└──────────────────────┼──────────────────────────────────────┘
                       ▼
                  /data/nexus.db (file, host bind mount)
```

**Pain points:**
- Single writer task is a hard bottleneck (queue depth >800 already triggers warning).
- Reads share one connection — true concurrency is cooperative only.
- Schema migrations are ad-hoc DDL in `_create_schema()`; no migration history.
- No analytical queries (no JSON ops, no LATERAL, no `RETURNING` chains).
- `.fetchall()` over an entire result is the only ergonomic path; streaming uses `fetchmany`.

### Target (PostgreSQL — connection pool + native MVCC)

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI workers=1 (asyncio event loop)                     │
│                                                             │
│   ┌──────────┐    ┌──────────┐   ...  ┌──────────┐          │
│   │ Endpoint │    │ Agent #1 │        │ Agent #N │          │
│   └────┬─────┘    └────┬─────┘        └────┬─────┘          │
│        │  acquire()    │ acquire()         │ acquire()      │
│        ▼               ▼                   ▼                │
│   ┌──────────────────────────────────────────────┐          │
│   │  asyncpg.Pool  (min=2, max=12)               │          │
│   │  command_timeout=30s, max_inactive=300s      │          │
│   └──────────────────┬───────────────────────────┘          │
└──────────────────────┼──────────────────────────────────────┘
                       │ TCP (docker network: nexus_net)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  postgres:16-alpine container                               │
│   shared_buffers=256MB | work_mem=8MB | maintenance=64MB    │
│   max_connections=30   | effective_cache_size=768MB         │
│   wal_compression=on   | synchronous_commit=on              │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
                postgres_data (named volume)
```

**Wins:**
- MVCC: every connection writes concurrently. No write queue. No serializer task.
- Real schema migrations via Alembic (history table, up/down, environment-aware).
- Natural row-level locking (`SELECT ... FOR UPDATE SKIP LOCKED`) for future job queues.
- Streaming results via `cursor()` inside a transaction — no `fetchmany` workarounds.

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| `api/db.py` (rewritten) | Owns `asyncpg.Pool`, exposes `read_one/read_all/write/write_await/read_stream/transaction()` | All routes, services, agents |
| `api/migrations/` (new) | Alembic environment + versioned SQL migrations | CI/CD, container entrypoint |
| `postgres` (new container) | DB engine + WAL + checkpoints | `nexus` container only (private docker network) |
| `nexus` (FastAPI container) | App logic; no longer mounts `/data` for the DB file | `postgres` via TCP |
| `tests/conftest.py` (rewritten) | Spins up ephemeral test DB (template-based clone) | pytest fixtures |

---

## Connection Pool Sizing — concrete numbers for 4GB VPS, 10 concurrent agents

**Reasoning:**
- Hard ceiling in code: `asyncio.Semaphore(10)` for agents + 1-2 endpoint handlers in flight.
- One connection per concurrently active coroutine is the asyncpg pattern; reuse via pool.
- Each idle Postgres backend ≈ 8-12MB RSS. 12 connections ≈ ~120-150MB worst case.
- Math: 4GB total − 500MB OS − 300MB FastAPI app − 600MB Postgres shared (buffers + cache) = ~2.6GB headroom; 150MB for backends fits comfortably.

```python
# api/db.py (target)
self._pool = await asyncpg.create_pool(
    dsn=settings.DATABASE_URL,
    min_size=2,             # warm pool — first scan never pays cold-start
    max_size=12,            # 10 agents + 2 endpoint slots; matches Semaphore(10)
    max_inactive_connection_lifetime=300.0,  # recycle idle conns every 5min
    command_timeout=30.0,   # any single statement >30s = abort + log
    server_settings={
        "application_name": "nexusosint",
        "jit": "off",           # JIT costs more than it saves on small queries
        "timezone": "UTC",
    },
)
```

Postgres side: `max_connections=30` (12 app + 5 admin/maintenance + headroom).

---

## Schema Migration Approach — RECOMMENDATION: Greenfield + selective preserve

**Recommendation: greenfield drop, preserve only `searches` audit log.**

Rationale (per existing tables in `api/db.py:130-186` — `searches`, `token_blacklist`, `rate_limits`, `quota_log`):
- `token_blacklist`: ephemeral by definition (entries expire). Drop. Force re-login post-migration (already a planned event for F7-style deploys).
- `rate_limits`: rolling window. Drop. Worst case: rate limits reset once.
- `quota_log`: nice-to-have, not critical. Drop, restart fresh series.
- `searches`: audit log — **preserve**. This is the only table with historical value.

This dramatically reduces migration risk: one table to port, three to recreate empty.

### Phased plan

```
Phase 1 (greenfield prep):
  - Stand up postgres container alongside SQLite
  - Apply Alembic baseline migration → all tables empty in PG
  - App still reads/writes SQLite

Phase 2 (data port):
  - Quiesce app (maintenance window: ~5 min)
  - Run port_searches.py → reads from sqlite (read_stream), inserts into PG via COPY
  - Verify row counts match: SELECT COUNT(*) FROM searches both sides

Phase 3 (cutover):
  - Flip DATABASE_URL env to postgres://...
  - Restart nexus container
  - Smoke test /health, /search, /admin
  - SQLite file kept on disk for 14 days as cold backup, then archived
```

---

## Data Export Strategy — Python script with COPY (NOT pg_restore)

`sqlite3 .dump` produces SQLite-flavored SQL (different types, no `BIGSERIAL`, no `TIMESTAMPTZ`, different quoting). `pg_restore` cannot consume it. Don't try.

**Use a small Python script with `asyncpg.Connection.copy_records_to_table` — fastest path, type-safe, no shell munging.**

`searches` table source schema (verbatim from `api/db.py:130-145`):
- `id INTEGER PRIMARY KEY AUTOINCREMENT` → PG `BIGSERIAL PRIMARY KEY`
- `ts TEXT NOT NULL` (ISO-8601 string, e.g. `"2026-05-07T14:32:11.123456"`) → PG `TIMESTAMPTZ`
- `username TEXT NOT NULL` → `TEXT NOT NULL`
- `ip TEXT` → `INET` (or keep `TEXT` for simplicity)
- `query TEXT NOT NULL`, `query_type TEXT`, `mode TEXT` → unchanged
- `modules_run TEXT` (CSV string) → `TEXT[]` array (parse on port)
- `breach_count / stealer_count / social_count INTEGER DEFAULT 0` → `INT DEFAULT 0`
- `elapsed_s REAL` → `DOUBLE PRECISION`
- `success INTEGER DEFAULT 1` → `BOOLEAN DEFAULT TRUE`

```python
# scripts/port_searches.py — run once, in maintenance window
import asyncio, aiosqlite, asyncpg
from datetime import datetime
from pathlib import Path

SQLITE_PATH = Path("/data/nexus.db")
PG_DSN = "postgres://nexus:***@postgres:5432/nexus"

async def main() -> None:
    sqlite_conn = await aiosqlite.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = aiosqlite.Row
    pg = await asyncpg.connect(PG_DSN)

    try:
        batch: list[tuple] = []
        BATCH = 1000
        async with sqlite_conn.execute(
            "SELECT ts, username, ip, query, query_type, mode, modules_run, "
            "breach_count, stealer_count, social_count, elapsed_s, success "
            "FROM searches ORDER BY id"
        ) as cur:
            async for row in cur:
                ts = datetime.fromisoformat(row["ts"])    # SQLite TEXT → PG TIMESTAMPTZ
                modules = (row["modules_run"] or "").split(",") if row["modules_run"] else []
                batch.append((
                    ts, row["username"], row["ip"], row["query"], row["query_type"],
                    row["mode"], modules, row["breach_count"],
                    row["stealer_count"], row["social_count"], row["elapsed_s"],
                    bool(row["success"]),
                ))
                if len(batch) >= BATCH:
                    await pg.copy_records_to_table(
                        "searches",
                        records=batch,
                        columns=["ts","username","ip","query","query_type","mode",
                                 "modules_run","breach_count","stealer_count",
                                 "social_count","elapsed_s","success"],
                    )
                    batch.clear()
        if batch:
            await pg.copy_records_to_table("searches", records=batch, columns=[
                "ts","username","ip","query","query_type","mode","modules_run",
                "breach_count","stealer_count","social_count","elapsed_s","success",
            ])

        sqlite_count = (await (await sqlite_conn.execute(
            "SELECT COUNT(*) FROM searches")).fetchone())[0]
        pg_count = await pg.fetchval("SELECT COUNT(*) FROM searches")
        assert sqlite_count == pg_count, f"Mismatch: sqlite={sqlite_count} pg={pg_count}"
        print(f"OK — ported {pg_count} rows")
    finally:
        await sqlite_conn.close()
        await pg.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Why COPY (not INSERT loop):** COPY is 10-50x faster and bypasses per-row WAL overhead — important for the audit table that may have 100k+ rows.

---

## What Code Dies When Postgres Replaces the Queue

Concrete deletions in `api/db.py` (verified against current source, lines noted):

```diff
- _STOP_SENTINEL = object()                                    # line 34
- self._write_queue: asyncio.Queue[Any] = ...                  # line 46
- self._writer_task: Optional[asyncio.Task[None]] = None       # line 47
- async def _writer_loop(self) -> None: ...                    # lines 193-222 — ENTIRE METHOD
- # queue-full handling, qsize warnings, sentinel shutdown logic in shutdown()
```

**The `write` / `write_await` API stays** (callers don't change), but the implementation becomes a one-liner against the pool:

```python
async def write(self, sql: str, params: tuple = ()) -> None:
    """Fire-and-forget write — Postgres MVCC handles concurrency natively."""
    if not self._pool:
        logger.warning("DB write before startup() — sql=%r", sql)
        return
    try:
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *params)
    except asyncpg.PostgresError as e:
        # Match current behavior: log, don't propagate
        logger.error("DB write error — sql=%r error=%s", sql, e)

async def write_await(self, sql: str, params: tuple = ()) -> None:
    """Write + await confirmation — same shape as before, no queue indirection."""
    if not self._pool:
        raise RuntimeError("DatabaseManager not started")
    async with self._pool.acquire() as conn:
        await conn.execute(sql, *params)  # raises asyncpg.PostgresError on failure
```

**SQL placeholder migration:** SQLite uses `?`, asyncpg uses `$1, $2, ...`. Either:
1. Audit all call sites and rewrite (greppable, ~30-50 spots — preferred).
2. Wrap with a `?`→`$N` translator at the db layer (hides the change but adds runtime cost).

Recommend option 1 — the codebase is small and the explicit form is clearer in PRs.

---

## Repository / Service Layer Changes

| Layer | Stays | Swaps |
|-------|-------|-------|
| Routes (`api/routes/*.py`) | All endpoint signatures, all business logic | Nothing — routes call `db.read_*` / `db.write*` (unchanged shapes) |
| Services (`api/services/*.py`) | All authorization, all validation | SQL placeholder syntax (`?` → `$1`) |
| `api/db.py` | Public method names | Internal: pool replaces queue/connection |
| `api/orchestrator.py` | TaskGroup, Semaphore, registry | Nothing — orchestrator never touched DB internals |
| `api/budget.py` | Logic | If it touches DB: placeholder syntax |
| `tests/conftest.py` | Pytest patterns | `:memory:` SQLite → ephemeral PG schema (see Testing) |

**Schema-level changes (PostgreSQL idiomatic):**
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGSERIAL PRIMARY KEY` (or `BIGINT GENERATED ALWAYS AS IDENTITY`).
- `TEXT` for timestamps → `TIMESTAMPTZ` (and store real datetimes, not ISO strings — kills a class of timezone bugs).
- `INTEGER DEFAULT 1` (boolean-ish) → `BOOLEAN DEFAULT TRUE` for `success`.
- `modules_run TEXT` (currently CSV) → `TEXT[]` array. Trivial to query (`'shodan' = ANY(modules_run)`).
- Add `CREATE INDEX CONCURRENTLY` in migrations to avoid lock storms (irrelevant on greenfield, critical later).

---

## Docker Compose Layout

```yaml
# docker-compose.yml (target)
services:
  postgres:
    image: postgres:16-alpine        # ~80MB; pin digest after first stable deploy
    container_name: nexus_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: nexus
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD_FILE: /run/secrets/pg_password
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
    secrets:
      - pg_password
    command: >
      postgres
      -c shared_buffers=256MB
      -c effective_cache_size=768MB
      -c work_mem=8MB
      -c maintenance_work_mem=64MB
      -c max_connections=30
      -c wal_compression=on
      -c synchronous_commit=on
      -c checkpoint_completion_target=0.9
      -c random_page_cost=1.1
      -c log_min_duration_statement=500
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - nexus_net
    deploy:
      resources:
        limits:
          memory: 768m
        reservations:
          memory: 400m
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus -d nexus"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  nexus:
    build: .
    depends_on:
      postgres:
        condition: service_healthy   # CRITICAL: app starts only after PG ready
    environment:
      DATABASE_URL: postgres://nexus@postgres:5432/nexus
      DATABASE_PASSWORD_FILE: /run/secrets/pg_password
    secrets:
      - pg_password
    networks:
      - nexus_net
    deploy:
      resources:
        limits:
          memory: 2500m              # reduced from 3500m — PG took 768m
        reservations:
          memory: 300m

networks:
  nexus_net:
    driver: bridge

volumes:
  postgres_data:                     # named volume — survives `docker compose down`

secrets:
  pg_password:
    file: ./secrets/pg_password.txt  # NOT committed; provisioned on VPS
```

**Key points:**
- `condition: service_healthy` — FastAPI literally cannot start until `pg_isready` returns 0. No "connection refused on first boot" race.
- Named volume `postgres_data` — `docker compose down` won't nuke data; only `down -v` does.
- Password via Docker secret, **not** env var (env vars leak via `docker inspect`).
- Postgres has no `ports:` mapping — only reachable from `nexus_net`. Public attack surface unchanged.

---

## Memory Budget — concrete config for 4GB total VPS

```
Total VPS RAM:                           4096 MB
─────────────────────────────────────────────────
OS + Docker daemon + sshd:               ~500 MB
FastAPI app (resting per CLAUDE.md):     ~300 MB
FastAPI app (peak with 10 agents):       ~800 MB
Postgres backends (12 conns × ~10MB):    ~120 MB
Postgres shared_buffers:                  256 MB
Postgres work_mem (per query, peak):     ~100 MB  (8MB × ~12 concurrent)
Postgres maintenance_work_mem:             64 MB  (only during VACUUM/CREATE INDEX)
Postgres OS file cache (effective_cache_size is hint, not allocation):
  → uses leftover OS page cache, ~600-1000 MB realistic
─────────────────────────────────────────────────
Sum (peak realistic):                  ~2.0-2.4 GB
Headroom:                              ~1.6-2.0 GB
1GB swap (per CLAUDE.md):                  safety net, should not be touched
```

**Postgres tuning rationale:**
- `shared_buffers=256MB`: ~25% of allocated container memory (768MB), classic PG ratio.
- `effective_cache_size=768MB`: hint to planner about OS cache — affects index vs seq-scan choice.
- `work_mem=8MB`: per-operation; 12 conns × 2 sorts × 8MB = 192MB worst case.
- `maintenance_work_mem=64MB`: only used during VACUUM/REINDEX/CREATE INDEX.
- `max_connections=30`: hard cap. App pool is 12; leaves 18 for ad-hoc admin (psql, pg_dump, monitoring).
- `wal_compression=on`: ~30% smaller WAL, trivial CPU cost.
- `random_page_cost=1.1`: SSD-appropriate. Default 4.0 is for spinning rust.
- `log_min_duration_statement=500`: any query >500ms gets logged → feeds future slow-query analysis.

---

## Rollback Plan

**Pre-migration snapshot (mandatory before cutover):**
```bash
# On VPS
cp /root/nexus-osint/data/nexus.db /root/nexus-osint/data/nexus.db.pre-pg-$(date +%Y%m%d)
docker tag nexus-osint-nexus:latest nexus-osint-nexus:pre-pg-backup
git rev-parse HEAD > /root/nexus-osint/PRE_PG_COMMIT.txt
```

**Rollback decision tree:**

| Failure mode | Action |
|--------------|--------|
| `port_searches.py` row-count mismatch | Abort cutover. App still on SQLite. Investigate. No rollback needed. |
| Postgres container fails healthcheck | App won't start (depends_on health gate). Revert `docker-compose.yml`, `docker compose up -d`. SQLite intact. |
| App boots but queries fail (placeholder bugs, etc.) | `git revert <migration commit>`, redeploy pre-pg image, app reads SQLite again. SQLite was untouched. |
| App stable for <24h then breaks | Same as above — SQLite snapshot is at most 24h stale (audit log only — non-critical loss). |
| App stable >24h, deep PG bug emerges | Forward-fix only. Reverse-port from PG to SQLite is not maintained. |

**Critical invariant:** SQLite file is **read-only after cutover**, kept for 14 days. Don't delete until app is confirmed stable.

---

## Testing Strategy

**Current pattern:** `aiosqlite.connect(":memory:")` per test — fast, isolated, zero infrastructure.

**Target pattern:** template-database cloning. Postgres has no `:memory:`, but `CREATE DATABASE nexus_test_xyz TEMPLATE nexus_test_template` is fast (~50ms — file copy at FS level).

```python
# tests/conftest.py (target)
import os, uuid, asyncpg, pytest

PG_ADMIN_DSN = os.getenv("TEST_PG_ADMIN_DSN", "postgres://postgres:postgres@localhost:5433/postgres")
TEMPLATE_DB = "nexus_test_template"

@pytest.fixture(scope="session", autouse=True)
async def _prepare_template():
    """Build the template DB once per test session: schema applied, no data."""
    admin = await asyncpg.connect(PG_ADMIN_DSN)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS {TEMPLATE_DB}')
        await admin.execute(f'CREATE DATABASE {TEMPLATE_DB}')
    finally:
        await admin.close()

    template_dsn = PG_ADMIN_DSN.rsplit("/", 1)[0] + f"/{TEMPLATE_DB}"
    os.environ["DATABASE_URL"] = template_dsn
    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield

@pytest.fixture
async def db_pool():
    """Per-test ephemeral DB cloned from template — full isolation, ~50ms cost."""
    test_db = f"nexus_test_{uuid.uuid4().hex[:8]}"
    admin = await asyncpg.connect(PG_ADMIN_DSN)
    try:
        await admin.execute(f'CREATE DATABASE {test_db} TEMPLATE {TEMPLATE_DB}')
    finally:
        await admin.close()

    test_dsn = PG_ADMIN_DSN.rsplit("/", 1)[0] + f"/{test_db}"
    pool = await asyncpg.create_pool(test_dsn, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
        admin = await asyncpg.connect(PG_ADMIN_DSN)
        try:
            await admin.execute(f'DROP DATABASE {test_db}')
        finally:
            await admin.close()
```

**docker-compose.test.yml** spins up a throwaway Postgres on port 5433 for CI:
```yaml
services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: postgres
    ports: ["5433:5432"]
    tmpfs: /var/lib/postgresql/data    # tmpfs = pure RAM, no disk, fastest possible
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 2s
      retries: 10
```

**Trade-off acknowledged:** test runs go from "zero infra" (SQLite `:memory:`) to "needs docker". Mitigation: keep a `pytest --no-pg` flag for pure-unit tests that don't exercise PG-specific SQL; integration/e2e always use real PG.

---

## Patterns to Follow

### Pattern 1: Always use the pool, never hold connections across awaits
**What:** `async with pool.acquire() as conn:` for the narrowest possible scope.
**When:** Every DB call.
**Why:** Holding a connection while awaiting an external HTTP call (e.g., agent fetch) starves the pool. With `max_size=12` and 10 agents each doing `acquire() → httpx.get() → release()`, you'd block all endpoints.

```python
# CORRECT
async def record_search(username: str, query: str) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute("INSERT INTO searches(...) VALUES($1, $2)", username, query)
    # connection released; now do slow work
    result = await some_external_api_call(query)

# WRONG — holds connection during HTTP call, drains pool
async def record_search_bad(username: str, query: str) -> None:
    async with db.pool.acquire() as conn:
        await conn.execute("INSERT INTO searches(...) VALUES($1, $2)", username, query)
        result = await some_external_api_call(query)  # ← connection idle, blocking pool slot
        await conn.execute("UPDATE searches SET result=$1 WHERE ...", result)
```

### Pattern 2: Streaming with cursor + transaction
**What:** Use `conn.cursor()` inside `conn.transaction()` for large result sets.
**When:** Replacement for current `read_stream` (>100 rows).

```python
async def stream_searches(since: datetime):
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            async for row in conn.cursor(
                "SELECT * FROM searches WHERE ts >= $1 ORDER BY ts", since
            ):
                yield dict(row)
```

### Pattern 3: `RETURNING` for single round-trip insert+id

```python
search_id = await conn.fetchval(
    "INSERT INTO searches(ts, username, query) VALUES($1, $2, $3) RETURNING id",
    datetime.utcnow(), username, query,
)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Re-implementing the asyncio.Queue write serializer "for safety"
**Why bad:** Postgres MVCC is the serializer. Adding a queue re-introduces the bottleneck the migration was meant to eliminate.
**Instead:** Trust the pool. If write contention shows up in benchmarks, tune `max_size` or add advisory locks for specific hot rows.

### Anti-Pattern 2: Setting `max_size` too high
**Why bad:** Postgres backends are not free — each costs ~10MB. 50 backends = 500MB. On a 4GB VPS this evicts page cache and tanks query speed.
**Instead:** Match max_size to actual concurrency (`Semaphore(10) + 2 = 12`).

### Anti-Pattern 3: Long-lived transactions
**Why bad:** Holds row locks, prevents VACUUM, bloats WAL.
**Instead:** Open transaction → do DB work → commit. External calls happen outside the transaction.

### Anti-Pattern 4: Connecting from outside the docker network
**Why bad:** Public Postgres = scanned within minutes, brute-forced within days.
**Instead:** `docker compose exec postgres psql ...` from the VPS. SSH tunnel for local tools.

---

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|-------------|--------------|-------------|
| Concurrent agents | 10 (current ceiling) | Add second app worker, share PG | Move PG to managed service (Hetzner/Neon/RDS) |
| `searches` table size | ~10MB | ~1GB — add monthly partitioning by `ts` | TimescaleDB extension or archive cold partitions |
| Connection pool | 12 (this milestone) | 12-20 per worker, 2 workers, PgBouncer in transaction mode | PgBouncer mandatory; managed PG with read replicas |
| Backups | `pg_dump` nightly via cron | `pg_dump` + WAL archiving (PITR) | Managed PG with continuous backup |
| Read scaling | N/A (single instance) | Add replica for analytics queries | Replica per region |

The migration as designed is correct for the next 10x of growth. Beyond that, the bottleneck shifts from "SQLite single writer" to "single Postgres host" — a much later problem.

---

## Sources

- asyncpg pool docs (HIGH): https://magicstack.github.io/asyncpg/current/api/index.html — `create_pool`, `copy_records_to_table`, cursor patterns
- PostgreSQL 16 server config (HIGH): https://www.postgresql.org/docs/16/runtime-config-resource.html — `shared_buffers`, `work_mem` semantics
- PostgreSQL Docker official image (HIGH): https://hub.docker.com/_/postgres — healthcheck conventions, init args
- Alembic async docs (HIGH): https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
- CLAUDE.md (HIGH, in-repo): hardware constraints, exception handling rules, deploy process
- `api/db.py` lines 34-222 (HIGH, in-repo): current public API surface and writer-loop code that will be deleted
