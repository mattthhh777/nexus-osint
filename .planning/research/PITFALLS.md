# Pitfalls Research

**Domain:** SQLite (aiosqlite) → PostgreSQL (asyncpg) migration for FastAPI on a constrained 4GB VPS
**Researched:** 2026-05-07
**Confidence:** HIGH (well-documented failure modes; verified against asyncpg, PostgreSQL 16, SQLAlchemy 2 docs)

---

## Critical Pitfalls

### Pitfall 1: SQL dialect drift — `AUTOINCREMENT`, `INSERT OR REPLACE`, `||` concat, `datetime()`

**What goes wrong:**
SQL that ran fine in SQLite explodes at runtime in Postgres. Examples that break:

```sql
-- SQLite (works)                          -- Postgres (broken)
CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, ...);
INSERT OR REPLACE INTO scans VALUES (...);
SELECT datetime('now');                    -- function does not exist
SELECT strftime('%Y', created_at);         -- function does not exist
SELECT 1 WHERE flag = 1;                   -- ok if flag is BOOLEAN? Only sometimes
SELECT a || b FROM t;                      -- works in both, BUT NULL || x = NULL in PG
WHERE rowid = 5                            -- ROWID does not exist
LIMIT 10 OFFSET 5                          -- ok, but `LIMIT -1` (SQLite "no limit") fails
```

Postgres equivalents:

```sql
CREATE TABLE t (id BIGSERIAL PRIMARY KEY, ...);  -- or GENERATED ALWAYS AS IDENTITY (preferred, SQL standard)
INSERT INTO scans (...) VALUES (...) ON CONFLICT (target_hash) DO UPDATE SET ...;
SELECT NOW();                                     -- or CURRENT_TIMESTAMP
SELECT EXTRACT(YEAR FROM created_at);
WHERE id = 5;                                     -- use the explicit PK
```

**Why it happens:**
SQLite is permissive: it accepts non-standard syntax, coerces types aggressively, and has its own datetime/string functions. Postgres is strict and ANSI-aligned. Code written against SQLite never had to obey the standard.

**How to avoid:**
- Audit every raw SQL string in the codebase before migration. `grep -rE "AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(|rowid"` is mandatory pre-flight.
- Replace `INSERT OR REPLACE` with `INSERT ... ON CONFLICT (...) DO UPDATE SET ...` — and decide explicitly whether you want UPSERT or INSERT-ignore (`ON CONFLICT DO NOTHING`).
- Prefer SQLAlchemy Core/ORM for new code so dialect translation happens automatically.
- Test suite must run against Postgres (testcontainers), not just SQLite `:memory:` — otherwise dialect bugs hide until production.

**Warning signs:**
`syntax error at or near "AUTOINCREMENT"`, `function datetime(unknown) does not exist`, `column "rowid" does not exist`. These show up at query time, not import time — easy to miss in a smoke test.

**Phase to address:** Pre-migration code audit + integration test suite running on real Postgres.

---

### Pitfall 2: Type mapping landmines — `TIMESTAMP` vs `TIMESTAMPTZ`, JSON TEXT vs JSONB, BOOLEAN

**What goes wrong:**
A direct schema port using "the closest type" silently corrupts data:

| SQLite | Naive Postgres port | Correct Postgres |
|---|---|---|
| `INTEGER PRIMARY KEY` | `INTEGER PRIMARY KEY` | `BIGINT GENERATED ALWAYS AS IDENTITY` (or UUID) |
| `TEXT` (ISO timestamp) | `TIMESTAMP` | `TIMESTAMPTZ` |
| `INTEGER` (0/1 boolean) | `INTEGER` | `BOOLEAN` |
| `TEXT` (JSON blob) | `TEXT` | `JSONB` |
| `BLOB` | `BLOB` (does not exist) | `BYTEA` |
| `REAL` | `REAL` (4 bytes, lossy) | `DOUBLE PRECISION` |
| `NUMERIC` (money) | `NUMERIC` | `NUMERIC(12,2)` with explicit precision |

The most damaging is `TIMESTAMP` (without time zone). It silently strips or assumes UTC depending on the client locale — you get correct-looking timestamps that drift on DST or when the container TZ changes.

**Why it happens:**
Auto-translation tools (pgloader defaults, `sqlite3-to-postgres` scripts) map TEXT-storing-ISO-dates to `TIMESTAMP WITHOUT TIME ZONE`. Devs accept the default because "it has the right value when I `SELECT`."

**How to avoid:**
- **Always `TIMESTAMPTZ`.** Never `TIMESTAMP`. Set `SET timezone = 'UTC';` at session level and store everything UTC.
- For booleans, migrate values explicitly: `UPDATE t SET flag_bool = (flag_int <> 0)` then drop the int column.
- JSON columns: pick `JSONB` (binary, indexable, deduplicated keys) — `JSON` is just validated text and is rarely the right choice.
- Money/quantities: `NUMERIC(p,s)` with explicit precision. Never `FLOAT`/`DOUBLE` for currency.
- Generate the new schema by hand or via SQLAlchemy with explicit types — do not trust auto-converters.

**Warning signs:**
Timestamps that read correctly in `psql` but display 3h off in the UI. Boolean filters returning empty (`WHERE active = 1` rejected: `operator does not exist: boolean = integer`). JSON queries that work but cannot be indexed.

**Phase to address:** Schema design phase, before any data is moved.

---

### Pitfall 3: Boolean strictness — `0`/`1` and `'true'`/`'false'` strings rejected

**What goes wrong:**
```python
# Worked in SQLite (everything is text/integer under the hood)
await conn.execute("INSERT INTO users (active) VALUES (?)", (1,))
await conn.execute("SELECT * FROM users WHERE active = ?", ("true",))

# In asyncpg → asyncpg.exceptions.DataError: invalid input for query argument $1:
#   1 (a boolean is required, not int)
```

Postgres + asyncpg do **not** coerce. `1`, `0`, `"true"`, `"1"` are all rejected for `BOOLEAN` columns. SQLAlchemy hides this; raw asyncpg does not.

**Why it happens:**
SQLite has no real BOOLEAN type — values are integers. asyncpg enforces strict Python ↔ Postgres type mapping (`bool` ↔ `BOOLEAN`).

**How to avoid:**
- Audit all places that pass integers/strings to boolean columns. Convert at the boundary: `bool(value)`.
- Pydantic models should already give you `bool`. If a legacy code path passes `1`, fix the call site, not the column.
- Migration script must do `CAST(int_col AS BOOLEAN)` or explicit `CASE WHEN int_col <> 0 THEN TRUE ELSE FALSE END`.

**Warning signs:**
`invalid input for query argument $N: 1 (a boolean is required, not int)` from asyncpg.

**Phase to address:** Pre-migration code audit + integration test pass.

---

### Pitfall 4: asyncpg API differs from aiosqlite — placeholders, return types, transactions

**What goes wrong:**
Naive find-replace from `aiosqlite` to `asyncpg` breaks every query:

```python
# aiosqlite                                    # asyncpg equivalent
await conn.execute("SELECT * FROM t WHERE id = ?", (5,))
await conn.execute("SELECT * FROM t WHERE id = $1", 5)   # $1, not ?, args not in tuple

cursor = await conn.execute("SELECT ...")     # aiosqlite returns a cursor
row = await cursor.fetchone()                 # row is a tuple
val = row[0]
                                              # asyncpg: no cursor pattern
row = await conn.fetchrow("SELECT ...")       # returns a Record (dict-like)
val = row['col']                              # access by name OR index

await conn.commit()                           # aiosqlite: explicit commit needed
                                              # asyncpg: autocommit by default
                                              # use `async with conn.transaction():` for explicit txns
```

Other API breakages:
- `conn.execute()` in asyncpg returns a status string (`"INSERT 0 1"`), not a cursor.
- `executemany` semantics differ — asyncpg is much faster but does not return rowcounts per row.
- `RETURNING` clause is the idiomatic way to get inserted IDs (Postgres feature, no SQLite equivalent).
- asyncpg does not use DB-API 2.0 — code written against `sqlite3`/`aiosqlite` patterns will not work.

**Why it happens:**
asyncpg is **not** a DB-API 2.0 driver. It's a custom high-performance async driver with its own API. People assume it's a drop-in replacement.

**How to avoid:**
- Wrap DB access behind a thin repository layer **before** migrating, so the swap is contained to one module.
- Or use SQLAlchemy 2.0 async (`create_async_engine("postgresql+asyncpg://...")`) which abstracts both drivers — simplest path.
- If using raw asyncpg: write a small adapter (`db.fetch_one`, `db.execute`) and migrate call sites mechanically.

**Warning signs:**
`syntax error at or near "?"` (placeholder mismatch). `'str' object has no attribute 'fetchone'` (treating execute() return as cursor). Silent missing commits in code that previously needed `await conn.commit()`.

**Phase to address:** API abstraction phase, before driver swap.

---

### Pitfall 5: Connection leaks under `asyncio.TaskGroup` cancellation

**What goes wrong:**
With the existing pattern (TaskGroup + Semaphore(10) + agents) and a Postgres connection acquired per task, cancellation can leak connections back to the pool in a broken state:

```python
async def agent_task(pool, target):
    conn = await pool.acquire()         # ← acquired
    try:
        await conn.fetch("...")          # ← TaskGroup cancels here mid-query
        await conn.execute("...")
    finally:
        await pool.release(conn)         # may not run cleanly under CancelledError
```

Symptoms: pool exhausts after a few cancelled scans. `pool.acquire()` blocks forever. Health endpoint reports "degraded" with no obvious cause.

**Why it happens:**
- `asyncio.CancelledError` propagates aggressively. If `release()` is interrupted or the connection has an in-flight query, asyncpg marks it broken — but the pool semaphore slot may not be freed correctly in older versions.
- Worse: if a transaction was open at cancel time, the connection sits in `IDLE IN TRANSACTION` on the Postgres side, holding locks.

**How to avoid:**
- Use `async with pool.acquire() as conn:` — context manager is cancel-safe.
- Better: `async with conn.transaction():` for any multi-statement work. Cancel inside the block triggers ROLLBACK automatically.
- Never store `pool.acquire()` results in instance attributes for use across awaits.
- Set `pool` with `command_timeout=30` and Postgres-side `idle_in_transaction_session_timeout = '60s'` — kills zombie transactions.
- Health endpoint should report `pool.get_size()` and `pool.get_idle_size()` — if `idle == 0` consistently, you have a leak.

```python
# CORRECT pattern under TaskGroup
async def agent_task(pool, target):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.fetch("...")
            await conn.execute("...")
    # cancellation at any point: connection released, transaction rolled back
```

**Warning signs:**
`asyncpg.exceptions.TooManyConnectionsError`, pool acquire timeouts, `pg_stat_activity` showing `idle in transaction` rows that never go away.

**Phase to address:** Connection pool integration phase — must be in place before agents touch Postgres.

---

### Pitfall 6: Transaction isolation difference — SQLite serialized vs Postgres READ COMMITTED

**What goes wrong:**
SQLite effectively runs at SERIALIZABLE — only one writer at a time, readers see a consistent snapshot of the last commit. Code written against SQLite often assumes "if I read X then write based on X, nobody changed X in between." Postgres default is READ COMMITTED — between your `SELECT` and your `UPDATE`, another transaction can modify the row.

```python
# Race condition that NEVER fires in SQLite, fires often in Postgres
async def increment_scan_count(conn, target_id: int):
    row = await conn.fetchrow("SELECT count FROM scans WHERE id = $1", target_id)
    new_count = row['count'] + 1
    await conn.execute("UPDATE scans SET count = $1 WHERE id = $2", new_count, target_id)
    # Two agents running this in parallel: both read count=5, both write count=6.
    # Final value: 6 (lost increment). SQLite serialized writes — never happens there.
```

**Why it happens:**
SQLite's locking model masks classic concurrency bugs. The code "works" until it runs on Postgres with real concurrency.

**How to avoid:**
- For counters and accumulators: use atomic SQL — `UPDATE scans SET count = count + 1 WHERE id = $1`.
- For read-modify-write logic that cannot be atomic: use `SELECT ... FOR UPDATE` to take a row lock, inside a transaction.
- For multi-row consistency: `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` or `SERIALIZABLE` for the specific transaction (not globally — performance cost).
- Audit every `SELECT` followed by an `UPDATE` based on the result. These are race-condition candidates.

**Warning signs:**
Counters drifting under load. Duplicate-key errors on inserts that "checked first." Lost updates that only show under concurrent scans.

**Phase to address:** Code audit phase + concurrency stress test against Postgres before cutover.

---

### Pitfall 7: Postgres OOM on a 4GB shared VPS — default config is too greedy

**What goes wrong:**
Postgres default `shared_buffers = 128MB` is fine, but **`work_mem = 4MB` is per-sort-per-connection**. With `max_connections = 100` (default) and 10 concurrent agents each doing a sort, peak RAM can hit `100 × 4MB × 2-3 sorts = 800MB-1.2GB` on top of everything else. Add FastAPI (~300MB resting), nginx, Docker overhead, and the VPS swaps or OOM-kills.

The CLAUDE.md hardware budget is unforgiving:
- VPS: 4GB total
- App resting: <500MB target
- Alert at 2000MB used
- Critical at 85% (~3400MB)
- Postgres must fit comfortably under ~1GB total to leave headroom.

**Why it happens:**
Defaults assume a dedicated DB host. Postgres docs (`postgresql.conf` defaults) are tuned for ≥8GB dedicated machines. Nobody changes them on a small VPS until the OOM killer runs.

**How to avoid:**
Set explicit limits in `postgresql.conf` (or via `command:` in docker-compose):

```conf
# 4GB VPS shared with FastAPI — budget Postgres at ~800MB-1GB max
shared_buffers = 256MB              # 25% of allocated PG budget, NOT of system RAM
effective_cache_size = 1GB          # hint only, no allocation
work_mem = 8MB                      # per sort/hash op — keep low
maintenance_work_mem = 64MB         # for VACUUM, CREATE INDEX
max_connections = 20                # asyncpg pool max=10 + slack — DO NOT default to 100
wal_buffers = 8MB
synchronous_commit = on             # safety > speed for OSINT scan data
checkpoint_completion_target = 0.9
random_page_cost = 1.1              # SSD
effective_io_concurrency = 200      # SSD
```

Docker compose memory limit:

```yaml
postgres:
  deploy:
    resources:
      limits:
        memory: 1g                  # hard cap
      reservations:
        memory: 256m
```

`max_connections = 20` is the most important: every connection consumes ~10MB even idle. The asyncpg pool of 10 + a handful of admin sessions covers the load (the app is constrained to Semaphore(10) anyway).

**Warning signs:**
`docker stats` showing postgres > 1GB. `dmesg | grep -i kill` showing OOM events. App reporting `connection refused` after sustained load.

**Phase to address:** Postgres configuration phase, before first production cutover.

---

### Pitfall 8: Docker Compose startup race — app connects before Postgres is ready

**What goes wrong:**
```yaml
services:
  app:
    depends_on:
      - postgres            # ← only waits for container start, NOT readiness
```

Postgres takes 5-10 seconds (longer on first run with `initdb`) before `pg_isready` returns success. The FastAPI app starts immediately, tries to connect, fails, and either crashes or sits in retry-loop spam.

**Why it happens:**
`depends_on` (without conditions) only orders **start**, not readiness. This is documented but routinely missed.

**How to avoid:**
```yaml
services:
  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  app:
    depends_on:
      postgres:
        condition: service_healthy   # ← waits for healthcheck pass
```

Plus: app code must still implement connection retry with backoff for restart scenarios (`postgres` container restarted while `app` running). asyncpg `create_pool()` accepts no built-in retry — wrap it:

```python
async def connect_with_retry(dsn: str, attempts: int = 10) -> asyncpg.Pool:
    for i in range(attempts):
        try:
            return await asyncpg.create_pool(dsn, min_size=2, max_size=10, command_timeout=30)
        except (OSError, asyncpg.CannotConnectNowError) as e:
            await asyncio.sleep(min(2 ** i, 30))
    raise RuntimeError("Postgres unreachable after retries")
```

**Warning signs:**
App logs flooded with `Connection refused` on first deploy. Container restart loops. Healthcheck passing but app never becomes ready.

**Phase to address:** Docker Compose deployment phase.

---

### Pitfall 9: Volume permissions — postgres UID 999 vs host user

**What goes wrong:**
The official `postgres` image runs as UID 999 (`postgres` user inside the container). When you mount a host directory (`./data:/var/lib/postgresql/data`), the container fails with:

```
FATAL: data directory "/var/lib/postgresql/data" has wrong ownership
```

Or worse: it works on the dev machine (where the volume is created with permissive perms) but fails on the VPS where the directory was pre-created as root.

**Why it happens:**
Postgres refuses to start if the data dir is owned by anyone except its own UID — security feature, not a bug. Bind-mounted host paths inherit host ownership.

**How to avoid:**
Three options, in order of preference:

1. **Use a named Docker volume** (recommended):
   ```yaml
   volumes:
     postgres_data:

   services:
     postgres:
       volumes:
         - postgres_data:/var/lib/postgresql/data
   ```
   Docker manages permissions internally. Backups via `docker exec pg_dump`.

2. **Bind mount with explicit chown** (if you need host-visible files):
   ```bash
   sudo mkdir -p /var/lib/nexus/postgres
   sudo chown -R 999:999 /var/lib/nexus/postgres
   sudo chmod 700 /var/lib/nexus/postgres
   ```

3. **Set user in compose** (last resort, breaks some image features):
   ```yaml
   user: "1000:1000"   # match host user
   ```

Recall the prior NexusOSINT deployment incident: `static/` had 700 perms, blocking nginx — same class of bug (UID mismatch + restrictive mode). Apply the lesson here.

**Warning signs:**
`FATAL: data directory ... has wrong ownership`. `Permission denied` on `pg_wal/`. Container exits immediately on start.

**Phase to address:** VPS deployment phase + add to existing `project_deployment_vps.md` memory.

---

### Pitfall 10: Backup/restore — `pg_dump` from outside vs inside the container, encoding

**What goes wrong:**
- Running `pg_dump` from the host with version mismatch (`pg_dump 14` against `postgres 16` server) → `server version mismatch` error or silently incomplete dumps.
- Dumps with default encoding on a host with `LANG=C` produce ASCII-mangled UTF-8 (Brazilian Portuguese accents, OSINT target names with non-Latin characters get corrupted).
- Restore on a different VPS fails because target collation differs.
- Forgetting to dump BOTH schema and data, or dumping with `--data-only` then trying to restore on an empty DB.

**Why it happens:**
`pg_dump` is highly version-sensitive (newer dump → older server fails; older dump → newer server usually works but loses features). Encoding follows the client locale by default, not the database's actual encoding.

**How to avoid:**
- **Always run `pg_dump` inside the container** — version match guaranteed:
  ```bash
  docker exec nexus-postgres pg_dump \
    -U nexus -d nexus_osint \
    --format=custom --no-owner --no-acl \
    --encoding=UTF8 \
    > backup_$(date +%Y%m%d_%H%M%S).dump
  ```
- Use `--format=custom` (binary) — supports parallel restore, selective restore, smaller files.
- Pin Postgres image to a specific minor version (`postgres:16.4-alpine`), never `postgres:latest`.
- Set `POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale=C.UTF-8"` on first init.
- Test restore on a fresh container BEFORE you need it. A backup you have not restored is not a backup.

```bash
# Restore drill — run weekly on staging
docker run --rm -v $PWD:/backup postgres:16.4-alpine \
  pg_restore --list /backup/backup_latest.dump | head
```

**Warning signs:**
`pg_dump: server version: 16.x; pg_dump version: 14.x`. Question marks instead of accented characters in restored data. Restore that "succeeds" but row counts differ.

**Phase to address:** Backup/recovery phase, with a restore drill before cutover.

---

### Pitfall 11: Migration window — silent data loss during cutover

**What goes wrong:**
Naive cutover plan: "stop app, dump SQLite, load into Postgres, start app." Reality:

1. App is stopped → users get errors → customer support fire.
2. Dump takes longer than expected because `VACUUM` was never run on the SQLite DB → 10 minute window stretches to 40.
3. New writes that arrived during cutover (queued in nginx buffer, retried by clients, scheduled scans) are lost — they hit the new Postgres DB but reference IDs from the old SQLite DB that did not migrate consistently.
4. Auto-increment sequences in Postgres start from 1 — collide with imported data → `duplicate key value violates unique constraint`.

**Why it happens:**
Migrations are tested with static datasets. Production has continuous writes. Sequence reset is forgotten because SQLite's `AUTOINCREMENT` is not a separate object.

**How to avoid:**
Pre-flight checklist:

1. **Schedule a maintenance window** (per CLAUDE.md regra: "Deploy de mudanças de schema de banco de dados exige janela de manutenção planejada"). Notify users.
2. **Read-only mode toggle** in the app (env var or feature flag) — accepts GETs, returns 503 with `Retry-After` for writes. Better UX than full downtime.
3. **Stop writes** → wait for inflight scans to complete (poll `orchestrator._registry`, max 60s) → snapshot SQLite.
4. **Migrate** with a tested script. Time it on a staging copy of production first.
5. **Reset Postgres sequences** after import:
   ```sql
   SELECT setval(pg_get_serial_sequence('scans', 'id'), MAX(id)) FROM scans;
   -- repeat per table with serial PKs
   ```
6. **Verify row counts** per table match between old and new DB. Hash a sample of rows.
7. **Switch DSN, restart app, exit read-only mode.**
8. **Keep the SQLite snapshot for 30 days** — your only rollback path if drift is found later.

**Warning signs:**
After cutover: `duplicate key value violates unique constraint "scans_pkey"` on first insert (sequences not reset). Users reporting "my scan from this morning is missing." Inconsistent row counts.

**Phase to address:** Cutover plan phase — separate from schema/data migration phases.

---

### Pitfall 12: Forgotten autovacuum tuning on bulk-write tables

**What goes wrong:**
Default autovacuum thresholds (`autovacuum_vacuum_scale_factor = 0.2`) mean a table needs 20% dead tuples before vacuum runs. On a high-churn table like `scans` (rapid inserts + occasional deletes from cleanup jobs), this means hundreds of MB of bloat before reclaim. On the 80GB VPS disk, bloat compounds — query plans degrade as the table physical size grows past the actual data size.

**Why it happens:**
Defaults are conservative for low-write workloads. OSINT scan data is bursty and frequently rewritten (status updates, result merging) — exactly the workload the defaults punish.

**How to avoid:**
Per-table tuning for high-churn tables:

```sql
ALTER TABLE scans SET (
  autovacuum_vacuum_scale_factor = 0.05,   -- vacuum at 5% bloat instead of 20%
  autovacuum_analyze_scale_factor = 0.02,
  autovacuum_vacuum_cost_delay = 10        -- gentle, don't impact app
);
```

Monitor bloat with:
```sql
SELECT relname, n_dead_tup, n_live_tup,
       round(100.0 * n_dead_tup / NULLIF(n_live_tup,0), 2) AS dead_pct
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
```

**Warning signs:**
Disk usage growing faster than data. Query plans switching from index scan to seq scan over time. `pg_stat_user_tables.n_dead_tup` over 10% of `n_live_tup`.

**Phase to address:** Post-migration tuning phase, with a 1-week observation period.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip the abstraction layer; sed-replace `aiosqlite` → `asyncpg` directly | Saves a day | Every query has dialect bugs hiding in it; impossible to test against both DBs | Never — write the repository layer first |
| Use SQLAlchemy ORM only "to ease migration" then keep it everywhere | Easy dialect translation | ORM overhead, N+1 queries, harder to optimize | Acceptable if profiled; hot paths can drop to raw SQL |
| `TIMESTAMP` instead of `TIMESTAMPTZ` because "we always store UTC anyway" | One char shorter | Silent corruption when container TZ changes; DST bugs | Never |
| Default `max_connections = 100` because "we'll tune later" | Postgres starts | OOM on first sustained load | Never on a 4GB VPS |
| Skip the read-only mode and just take 10 min downtime | Simpler cutover code | User-visible errors, support load, data loss for retried writes | Acceptable for <100 users on internal tool; not for production OSINT users |
| Single `postgres` superuser for the app | One env var | If app is compromised, attacker has DDL rights | Acceptable for v1; harden with a separate `nexus_app` role with table-level grants in v4.3+ |
| No `pgbouncer` because "asyncpg has a pool" | One less moving part | Fine — actually correct on a single-app VPS; revisit only if multi-instance | Always for this deployment shape |
| Keep the asyncio.Queue single-writer pattern after Postgres migration | Code reuse | Wastes Postgres's MVCC concurrency; serializes writes unnecessarily | Never — drop the queue, let Postgres handle write concurrency |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| asyncpg + PgBouncer (transaction mode) | Prepared statement cache breaks — PgBouncer reuses connections across clients, statements vanish | Disable cache: `asyncpg.create_pool(..., statement_cache_size=0)`. Or use session mode (defeats PgBouncer's purpose). For NexusOSINT: just don't use PgBouncer — single app, asyncpg pool is enough |
| SQLAlchemy 2.0 async + asyncpg | Forgetting `await session.commit()` — autocommit is OFF | Use `async with session.begin():` block, commit is automatic |
| Alembic migrations + async engine | Default Alembic env.py is sync — fails with async URL | Use the async template: `alembic init -t async migrations` |
| Postgres + Docker logs | `log_statement = 'all'` floods `docker logs`, fills disk on 80GB VPS | Set `log_min_duration_statement = 1000` (only slow queries); ship logs to file with rotation |
| pg_dump + cron in container | Container restarts lose cron jobs | Run backups from host cron via `docker exec`, write to host-mounted dir |
| asyncpg + uvloop | Silently faster, but `loop.run_until_complete()` patterns may break | Use `asyncio.run()` and let asyncpg pick the loop; NexusOSINT already on stdlib asyncio — leave it |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No autovacuum tuning on bulk-write tables | Bloat grows; queries slow over weeks; 80GB disk fills | Per-table `autovacuum_vacuum_scale_factor = 0.05` | After ~100k rows of churn |
| `SELECT *` on JSONB columns transferred over the wire | Slow queries, network saturation | Select only needed fields; use `->>'field'` to extract scalars | When JSON blobs grow > 10KB each |
| Missing indexes on FKs | Sequential scans on join; slow under concurrent agents | Index every FK: `CREATE INDEX ON child(parent_id)` (Postgres does NOT auto-index FKs, unlike MySQL) | Beyond ~10k rows |
| Default `work_mem` too low → disk-based sorts | Slow ORDER BY/GROUP BY queries; temp files in `pg_stat_tmp` | Tune `work_mem` per session for known-heavy queries: `SET LOCAL work_mem = '32MB'` | Reports/aggregations over >1k rows |
| Connection pool min_size = 0 | Cold-start latency on every request after idle | `min_size=2, max_size=10` — keep warm connections | Always under burst load |
| No statement timeout | One slow query holds a pool slot forever | `command_timeout=30` on pool + `statement_timeout = '30s'` in Postgres | Under any abnormal load |
| TOAST-ed JSONB with frequent updates | Slow writes; bloat | Split large JSON into a separate table or columnar fields if updated often | When JSON > 2KB and updated often |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| App connects as `postgres` superuser | SQL injection → DDL/full DB compromise | Create role `nexus_app` with `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES`; no DDL |
| `postgres` port 5432 exposed on VPS public interface | Brute force; CVE exposure | Bind only to `127.0.0.1` or Docker internal network: `ports: []` (no host mapping) |
| Plaintext password in `docker-compose.yml` committed to git | Credential leak | Use `.env` file (gitignored) referenced as `${POSTGRES_PASSWORD}`. Already an existing rule per CLAUDE.md |
| Logging full SQL with bound params | Target hashes / OSINT data in plain logs | `log_statement = 'ddl'` only; never `'all'` in production. Audit asyncpg debug logging |
| No `pg_hba.conf` hardening | Any local connection accepted with `trust` | Set `host all all 127.0.0.1/32 scram-sha-256`; never `trust` |
| Backup files in web-accessible path | Full DB download via misconfigured nginx | Backups outside any served directory; chmod 600; encrypt before off-site copy |
| SSL not enforced for connections | Container-to-container traffic on shared host visible to other tenants on shared infra | `ssl = on` in postgresql.conf; client `sslmode=require` |

---

## "Looks Done But Isn't" Checklist

- [ ] **Schema migration:** Verified TIMESTAMPTZ everywhere — `grep -i "TIMESTAMP[^T]" migrations/` returns zero
- [ ] **Schema migration:** Sequences reset to MAX(id) after data import — first new INSERT does not collide
- [ ] **Boolean columns:** All `0/1` values converted to true booleans — test query `SELECT * WHERE flag = TRUE` works
- [ ] **Connection pool:** `min_size >= 2`, `max_size <= 10`, `command_timeout` set — pool exhaustion test passes
- [ ] **Cancellation safety:** `pool.acquire()` always inside `async with` — grep for raw `await pool.acquire()` returns zero
- [ ] **Postgres config:** `max_connections = 20`, `work_mem = 8MB`, `shared_buffers = 256MB` — `SHOW max_connections;` confirms
- [ ] **Docker compose:** `depends_on: condition: service_healthy` — restarting postgres does not break app on first request
- [ ] **Volume:** Named volume or chown'd bind mount — `docker compose down && up` does not lose data
- [ ] **Backup:** `pg_dump` runs from cron, output verified by `pg_restore --list`, restore drill performed on staging
- [ ] **Encoding:** `SHOW server_encoding` returns `UTF8`; sample row with accented chars round-trips correctly
- [ ] **Cutover:** Read-only mode tested; row counts verified post-migration; rollback path documented
- [ ] **Sequences:** `SELECT setval(...)` ran for every table with a serial PK
- [ ] **Indexes:** Every FK has an index — `SELECT conname FROM pg_constraint WHERE contype='f'` cross-checked against `pg_indexes`
- [ ] **App user:** App connects as `nexus_app`, not `postgres` superuser — `SELECT current_user` from inside the app
- [ ] **Health endpoint:** Reports `pool.get_size()` and `pool.get_idle_size()` — leak detection in place
- [ ] **Logging:** No raw SQL with target data in production logs — verified by sampling 100 log lines
- [ ] **Concurrency:** Read-modify-write code paths replaced with atomic SQL or `SELECT FOR UPDATE`

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Sequence collision after import | LOW | `SELECT setval(pg_get_serial_sequence('t','id'), (SELECT MAX(id) FROM t));` per table |
| TIMESTAMP without TZ shipped to prod | MEDIUM | Add new TIMESTAMPTZ column; backfill with `old_col AT TIME ZONE 'UTC'`; swap; drop old |
| Boolean column with int values | LOW | `ALTER TABLE t ALTER COLUMN c TYPE BOOLEAN USING (c <> 0)` |
| Connection pool leak in production | MEDIUM | Restart app (immediate). Then add `idle_in_transaction_session_timeout` and audit `pool.acquire()` call sites |
| Postgres OOM-killed under load | MEDIUM | Lower `max_connections`, `shared_buffers`, `work_mem`; add Docker memory limit. May lose in-flight scans |
| Cutover lost writes | HIGH | Restore SQLite snapshot; replay missed writes from app logs; cross-reference scan IDs. This is why the snapshot must be kept 30 days |
| Wrong volume permissions | LOW | `docker compose down`; `chown -R 999:999 ./data`; `up`. No data loss if you fix before `initdb` runs |
| Wrong encoding (mojibake in data) | HIGH | If caught early: drop DB, recreate with `--encoding=UTF8`, reimport. If caught late: per-column `CONVERT_TO()` recovery, may be lossy |
| pg_dump version mismatch | LOW | Always exec inside container; this is preventive |
| Lost increment from RMW race | MEDIUM | Replace with atomic `UPDATE ... SET col = col + 1`; replay from logs if exact counts matter |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| SQL dialect drift | Pre-migration audit phase | Test suite green against Postgres testcontainer |
| Type mapping (TIMESTAMPTZ, JSONB, BOOL) | Schema design phase | `\d+ table_name` in psql; grep migration SQL |
| Boolean strictness | Code audit phase | Integration tests with real bool values |
| asyncpg API differences | Abstraction layer phase | Repository tests pass; no `?` placeholders in code |
| TaskGroup cancellation leaks | Pool integration phase | Cancel-storm test; `pg_stat_activity` clean after |
| Isolation-level race conditions | Code audit phase | Concurrent stress test; counters consistent |
| Postgres OOM tuning | Postgres config phase | `docker stats` < 1GB under load test |
| Compose startup race | Compose deployment phase | `docker compose restart postgres` does not break app |
| Volume permissions | VPS deployment phase | `down` + `up` preserves data |
| Backup/restore | Backup phase | Restore drill on staging passes |
| Cutover data loss | Cutover plan phase | Read-only mode + row count parity + sequence reset |
| Autovacuum on bulk tables | Post-migration tuning phase | Bloat report after 1 week of production |
| Missing FK indexes | Schema design phase | `EXPLAIN ANALYZE` on join queries shows index scan |

---

## Sources

- PostgreSQL 16 official docs — `postgresql.conf`, `pg_hba.conf`, `pg_dump` (HIGH confidence): https://www.postgresql.org/docs/16/
- asyncpg documentation — pool API, prepared statement caching, PgBouncer notes (HIGH): https://magicstack.github.io/asyncpg/current/
- SQLAlchemy 2.0 async docs (HIGH): https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Docker compose `depends_on` conditions (HIGH): https://docs.docker.com/compose/compose-file/05-services/#depends_on
- Postgres on small VPS tuning — pgtune defaults for ≤4GB (MEDIUM, community-corroborated): https://pgtune.leopard.in.ua/
- "PostgreSQL gotchas" community wiki (MEDIUM): https://wiki.postgresql.org/wiki/Don't_Do_This
- asyncpg + PgBouncer prepared statement issue tracker (HIGH): https://github.com/MagicStack/asyncpg/issues/339
- NexusOSINT internal: prior `static/` 700-perm incident — pattern reuse for postgres data dir (HIGH, project memory)
- CLAUDE.md hardware budget (HIGH, project policy): 4GB VPS, <500MB resting, <2000MB alert, <85% critical

---
*Pitfalls research for: SQLite (aiosqlite) → PostgreSQL (asyncpg) migration on 4GB VPS, single-app FastAPI deployment*
*Researched: 2026-05-07*
