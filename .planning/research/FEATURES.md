# PostgreSQL Features — NexusOSINT Migration

**Domain:** OSINT scanning platform — bursty agent writes + sustained dashboard reads
**Researched:** 2026-05-07
**Confidence:** HIGH (PostgreSQL 16 official docs + production patterns)
**Target version:** PostgreSQL 16.x (current stable, on Hetzner 4GB VPS)

This document is opinionated. Each feature is evaluated against NexusOSINT's exact workload — not theoretical generality. "ADOPT", "ADOPT LATER", or "SKIP" verdict for each.

---

## 1. JSONB — Variable Agent Result Schemas

**Verdict:** ADOPT (P1 — replaces `extra_fields TEXT` immediately)

**The problem in SQLite today:**
Maigret returns `{username, sites_found[], categories[]}`, Holehe returns `{email, services[], breaches[]}`, OathNet returns `{phone, carrier, registrations[]}`. Currently stored as serialized JSON in a `TEXT` column — opaque to queries. To answer "show all results where Maigret found GitHub" requires `LIKE '%github%'` (full table scan, no index).

**With JSONB:**
```sql
CREATE TABLE results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- GIN index: indexed lookups inside JSON
CREATE INDEX idx_results_payload_gin ON results USING GIN (payload jsonb_path_ops);

-- Query: scans where Maigret found github
SELECT search_id FROM results
WHERE agent = 'maigret'
  AND payload @> '{"sites_found": ["github"]}';
```

**Concrete NexusOSINT use cases:**
- Dashboard filter: "show searches where any agent found a Telegram presence" → indexed JSONB containment, sub-millisecond on 100k rows
- Audit query: "list all OathNet results with carrier=Vivo" → `payload->>'carrier' = 'Vivo'` with expression index
- Schema evolution: when Maigret adds a new field next release, no migration — JSONB absorbs it

**Caveat:** JSONB is ~10-20% larger on disk than TEXT. With 80GB SSD and per-result payloads <50KB, irrelevant.

---

## 2. Full-Text Search via tsvector — Search Across Past Scans

**Verdict:** ADOPT (P1 — kills a real product gap)

**The problem in SQLite today:**
SQLite has FTS5 but it's a separate virtual table requiring manual sync triggers. Currently NexusOSINT has no cross-scan search at all — Math has mentioned this is a frequent dashboard pain point.

**With Postgres tsvector + generated column:**
```sql
ALTER TABLE results ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(payload::text, ''))
    ) STORED;

CREATE INDEX idx_results_fts ON results USING GIN (search_vector);

-- Query: "find any past scan mentioning 'leaked' or specific email fragments"
SELECT search_id, agent, payload
FROM results
WHERE search_vector @@ websearch_to_tsquery('simple', 'leaked breach pwned');
```

**Why `simple` config (not `english` or `portuguese`):**
OSINT data is multilingual + technical (usernames, domains, phone fragments). Stemming corrupts identifiers (`running` → `run`). Use `simple` for OSINT — exact tokens matter.

**Use case:** Math wants to grep all historical scans for "any result containing this email fragment" → 50ms with GIN index vs minutes with `LIKE '%x%'` on TEXT.

---

## 3. Native UUID Type — Scan IDs

**Verdict:** ADOPT (P1 — quick win)

Currently scan IDs are likely TEXT or INTEGER autoincrement. UUIDs solve:

- **Distributed-safe IDs:** if NexusOSINT ever needs a worker on a separate process/host, no ID collision
- **Non-enumerable:** prevents `/api/scan/1`, `/api/scan/2` enumeration attacks (security relevance — frontend is hostile, per CLAUDE.md regra 3)
- **No sequence contention:** with concurrent agents writing, a UUID generated client-side has zero lock cost vs `nextval('seq')`

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

CREATE TABLE searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_hash TEXT NOT NULL,  -- per CLAUDE.md: never log raw target
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Use UUIDv7 (time-ordered, available via extension `pg_uuidv7` or generated in app code) if B-tree index locality on `id` matters for scan history pagination. UUIDv4 fragments the index — measurable on 1M+ rows but irrelevant at NexusOSINT scale.

---

## 4. Concurrent Writes (No More Single-Writer Queue)

**Verdict:** ADOPT (P1 — eliminates F2 architectural workaround)

**Today (CLAUDE.md F2):** SQLite + WAL still has single writer. NexusOSINT serializes writes through `asyncio.Queue + _write_worker`. This is correct for SQLite but adds latency: every agent's INSERT waits in queue.

**With Postgres MVCC:**
- 10 concurrent agents = 10 concurrent INSERTs, zero queueing
- Row-level locks only — no table or DB lock for writes to different rows
- WAL handles durability without serialization

**Quantified benefit for NexusOSINT workload:**
- SQLite (current): with 10 agents finishing ~simultaneously, last write waits ~9× the per-write latency. At ~5ms per insert = 45ms tail latency for the queue drain.
- Postgres: all 10 commit in parallel. Tail latency = max single-write latency (~2-3ms with `synchronous_commit=on`, ~0.5ms with `synchronous_commit=off` for non-critical writes).
- **~10-15× improvement on burst write tail latency.**

**Architectural simplification:**
```python
# DELETE this entire pattern from F2:
# - asyncio.Queue
# - _write_worker coroutine
# - future-based ack mechanism

# Replace with direct asyncpg pool:
async with pool.acquire() as conn:
    await conn.execute("INSERT INTO results ...", ...)
```

**Connection pool sizing on 4GB VPS:**
- Each Postgres backend = ~10MB resident
- Pool size 10-15 connections → ~100-150MB
- With `max_concurrent=10` agents (CLAUDE.md ceiling), pool of 12 is right

---

## 5. Partial Indexes — Hot Query Paths

**Verdict:** ADOPT (P2 — after baseline migration, profile first)

NexusOSINT has predictable hot paths the dashboard hits constantly:

```sql
-- Hot path: "show in-progress scans" (probably < 1% of total rows)
CREATE INDEX idx_searches_active ON searches (created_at DESC)
    WHERE status IN ('queued', 'running');

-- Hot path: budget tracking — only paid-tier
CREATE INDEX idx_budget_paid ON budget_tracking (user_id, billing_period)
    WHERE tier != 'free';
```

**Gotcha:** Postgres partial indexes cannot use `now()` or other volatile functions in the WHERE clause. For "recent failures" patterns, either use a fixed cutoff and rebuild periodically, or rely on a regular index ordered by `created_at DESC`.

**Benefit:** partial indexes are 10-100× smaller than full indexes when the predicate is selective. Faster scans, less RAM in shared_buffers, less write amplification.

**Profile-first rule:** add partial indexes only after migrating and observing actual slow queries via `pg_stat_statements`. Don't pre-optimize.

---

## 6. LISTEN/NOTIFY — Real-Time SSE Without Polling

**Verdict:** ADOPT (P2 — replaces dashboard polling, frees CPU)

**Today:** Dashboard likely polls `/api/scan/{id}/status` every 1-2s during a scan. With multiple users + multiple in-flight scans, this is a sustained load on FastAPI + SQLite reads.

**With Postgres NOTIFY:**
```sql
CREATE OR REPLACE FUNCTION notify_scan_update() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(
        'scan_updates',
        json_build_object('scan_id', NEW.id, 'status', NEW.status)::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_scan_notify
    AFTER UPDATE OF status ON searches
    FOR EACH ROW EXECUTE FUNCTION notify_scan_update();
```

```python
# FastAPI side — single listener task fans out to SSE clients
async def listen_loop(pool):
    async with pool.acquire() as conn:
        await conn.add_listener('scan_updates', dispatch_to_sse)
        while True:
            await asyncio.sleep(3600)  # keep-alive
```

**Quantified benefit:**
- Today: 10 concurrent dashboard users × poll/2s × 8h workday = ~144k pointless DB reads/day
- With NOTIFY: zero reads when nothing changes. Only push when status actually flips.

**Caveats:**
- NOTIFY payload max 8KB → only push IDs, dashboard fetches details on demand
- NOTIFY is at-most-once if listener is disconnected — handle reconnect by re-fetching state
- Don't use NOTIFY across processes/replicas without a real broker — not what it's for

---

## 7. Generated Columns vs Computed-on-Read

**Verdict:** ADOPT for `STORED` generated columns; SKIP `VIRTUAL` (not in Postgres 16; planned for later versions)

Postgres 16 only supports `GENERATED ALWAYS AS (...) STORED` (materialized at write).

**Use cases for NexusOSINT:**

```sql
-- Use case 1: tsvector for FTS (already shown in #2) — STORED is correct
search_vector tsvector GENERATED ALWAYS AS (...) STORED

-- Use case 2: derived flags for indexing
ALTER TABLE results
    ADD COLUMN has_breach BOOLEAN
    GENERATED ALWAYS AS ((payload ? 'breaches')) STORED;
CREATE INDEX idx_results_breach ON results (search_id) WHERE has_breach;

-- Use case 3: extracted JSONB scalars for fast filter
ALTER TABLE results
    ADD COLUMN target_username TEXT
    GENERATED ALWAYS AS (payload->>'username') STORED;
```

**Trade-off:**
- STORED: 1 write cost, fast read, indexable. Use when value is read >> written (NexusOSINT writes once per scan, reads on every dashboard hit — STORED wins).
- Computed-on-read (expression index): `CREATE INDEX ... ON results ((payload->>'username'))` — same query speed, no schema bloat, but doesn't appear as a column in `SELECT *`.

**Recommendation:** prefer expression indexes over generated columns where possible — less schema rigidity. Use generated columns only for `tsvector` (where the index needs the column) and for booleans queried frequently.

---

## 8. ENUM Types vs CHECK Constraints

**Verdict:** SKIP ENUM, USE CHECK (P1 — explicit decision, not a default)

Tempting:
```sql
CREATE TYPE scan_status AS ENUM ('queued','running','completed','failed','timeout');
```

**Why this is wrong for NexusOSINT:**
- Adding a new status (e.g., `'paused'` for F8 graceful degradation) requires `ALTER TYPE ... ADD VALUE`. Removing or reordering values is essentially impossible.
- ENUM values are stored as `oid` references — joining/comparing across DB dumps is fragile.
- The product is in active iteration. Schema flexibility > minor storage savings.

**Use this instead:**
```sql
CREATE TABLE searches (
    ...
    status TEXT NOT NULL CHECK (status IN (
        'queued','running','completed','failed','timeout','paused'
    ))
);
```

CHECK constraint can be modified with a single ALTER in a transaction. Storage cost (TEXT vs ENUM int): negligible at NexusOSINT scale.

---

## 9. Row-Level Security (RLS)

**Verdict:** SKIP for v4.2, REVISIT for v5.0 multi-tenant

**Why skip now:**
- NexusOSINT today is single-tenant per Math's product. RLS adds policy evaluation overhead on every query (~5-15% on read-heavy workloads) for zero benefit.
- The current authorization model lives in FastAPI (correct per CLAUDE.md regra 3 — backend-only). Pushing it into RLS doesn't add defense-in-depth here because the API role connects with full table privileges.

**When to revisit:**
- If/when NexusOSINT becomes multi-tenant SaaS (org-scoped data isolation)
- If a read-only analyst role is introduced
- Then: `CREATE POLICY org_isolation ON searches USING (org_id = current_setting('app.current_org')::uuid);` + `SET LOCAL app.current_org = '...'` per request.

**Don't half-adopt RLS** — it's all-or-nothing for security guarantees.

---

## 10. Logical Replication & Streaming Backup on 4GB VPS

**Verdict:** SKIP logical replication, ADOPT physical base backup + WAL archiving

**Reality check on this VPS:**
- Hetzner 3vCPU / 4GB RAM / 80GB SSD
- Postgres itself wants 512MB-1GB shared_buffers + work_mem per connection × 12 connections
- FastAPI + agents already target <500MB resting (CLAUDE.md)
- **No headroom for a hot standby on the same VPS.**

**Logical replication — SKIP:**
- Requires a *different* host as subscriber. Adds infra cost and ops complexity.
- Not needed: read replicas don't help NexusOSINT's workload (writes are the bottleneck, reads are <100 QPS dashboard traffic).

**Physical backup with `pg_basebackup` + WAL archiving — ADOPT:**
```bash
# Daily base backup to object storage (e.g., Hetzner Storage Box / S3)
pg_basebackup -D /backup/$(date +%F) -Ft -z -P --wal-method=stream

# Continuous WAL archiving in postgresql.conf:
archive_mode = on
archive_command = 'rclone copy %p backup:wal-archive/%f'
```

**RPO target:** 5 minutes (WAL ships every 5 min). **RTO:** ~30 min (download base + replay WAL on a fresh VPS).

For NexusOSINT's stage, this is sufficient. Don't over-engineer HA on a single 4GB VPS — it's a false sense of safety.

**Alternative (simpler):** `pg_dump` daily to Hetzner Storage Box. Loses point-in-time recovery but is operationally trivial. Acceptable for v4.2 launch; upgrade to WAL archiving once user data accumulates.

---

## 11. Performance vs SQLite WAL — Quantified for NexusOSINT Workload

**Verdict:** Postgres wins on writes by ~10×; SQLite slightly wins on simple reads.

### Concrete benchmark expectations (NexusOSINT pattern)

| Metric | SQLite WAL (current) | Postgres 16 | Winner |
|---|---|---|---|
| Single-row INSERT (agent result) | ~0.5ms | ~1-2ms (network + WAL) | SQLite (raw latency) |
| 10 concurrent INSERTs (burst) | ~5ms (queued) → tail ~45ms | ~2ms (parallel) | **Postgres** ~20× tail |
| Indexed point read | ~0.1ms (in-process) | ~0.3ms (network) | SQLite (raw latency) |
| JSONB containment query (100k rows) | full scan, ~100ms | GIN index, ~1-2ms | **Postgres** 50-100× |
| FTS across all results | not feasible without FTS5 setup | ~5-50ms | **Postgres** (only option) |
| Concurrent reads while writing | blocks on writer queue | non-blocking MVCC | **Postgres** |
| Bursty parallel agent writes | serialized (worst case) | linear scaling | **Postgres** |

**Key insight:** SQLite "wins" on raw single-op latency because there's no network round-trip — it's a library call. But NexusOSINT's actual bottleneck is **bursty concurrent writes** + **complex queries on JSON**, both of which favor Postgres dramatically.

**Memory cost on 4GB VPS:**
- SQLite: ~10MB total (in-process)
- Postgres: ~256MB shared_buffers + ~50MB per connection × 12 = ~850MB
- **Net cost of migration: ~800MB RAM.** With FastAPI at ~500MB, total = ~1.3GB. Leaves ~2.7GB for OS, swap headroom, agent runtime. Within budget per CLAUDE.md (`mem alert > 2000MB`).

**Recommended postgresql.conf tuning for 4GB VPS:**
```
shared_buffers = 768MB           # ~25% of available RAM after FastAPI
effective_cache_size = 1.5GB     # OS + Postgres cache combined
work_mem = 16MB                  # per sort/hash op; with ~12 connections = 192MB cap
maintenance_work_mem = 128MB
max_connections = 25             # hard cap; pool to 12-15
synchronous_commit = on          # keep ON for scan results (durability matters)
wal_compression = on             # cheap CPU win on slow disks
random_page_cost = 1.1           # SSD
```

---

## Feature Adoption Roadmap

### v4.2 Migration MVP (P1 — must adopt during migration)
- [x] JSONB for `results.payload`
- [x] Native UUID for all IDs (`gen_random_uuid()`)
- [x] Drop single-writer queue → asyncpg pool with concurrent writes
- [x] CHECK constraints (not ENUM) for status fields
- [x] Tuned `postgresql.conf` for 4GB VPS
- [x] `pg_basebackup` + nightly to object storage

### v4.3 Quick Wins (P2 — within 30 days of migration)
- [ ] tsvector + GIN index for cross-scan FTS (kills a known dashboard gap)
- [ ] LISTEN/NOTIFY for SSE dashboard updates (eliminates poll load)
- [ ] Profile via `pg_stat_statements`, add partial indexes on hot paths

### v5.0 Future (P3 — defer)
- [ ] WAL archiving for true PITR (when data volume justifies)
- [ ] Logical replication / read replicas (requires second host)
- [ ] Row-level security (only if multi-tenant)

---

## Anti-Features for NexusOSINT

| Feature | Why Tempting | Why Skip | Alternative |
|---|---|---|---|
| **ENUM types** | Looks cleaner than CHECK | Schema rigidity, painful migrations | TEXT + CHECK constraint |
| **Stored procedures (PL/pgSQL) for business logic** | "Push logic to DB for atomicity" | Violates CLAUDE.md — backend owns business rules; harder to test, debug, version | Logic in FastAPI; use SQL transactions for atomicity |
| **Triggers for derived data** | "Fire-and-forget consistency" | Hidden side effects, hard to reason about, breaks frontend tests | Generated columns or explicit writes |
| **Postgres FDW to external APIs** | "Query Shodan as a table" | Outbound HTTP from inside DB process — breaks rate limiting, error handling, observability | Stay in agent layer (CLAUDE.md OutboundRateLimiter) |
| **`pg_cron` for scheduled jobs** | Replaces app-level scheduler | Couples scheduling to DB, harder to scale, mixes concerns | APScheduler or systemd timer in app layer |
| **Postgres as message queue** | "We already have it" | Polling-based, doesn't scale, harder than dedicated queue | If queue needed → Redis or stay in-process asyncio |
| **GIN index on every JSONB column** | "JSONB is faster with GIN" | GIN indexes are large + slow to update on every write | Index only the JSONB columns the dashboard actually filters on |

---

## Sources

- PostgreSQL 16 official documentation (postgresql.org/docs/16/) — JSONB, FTS, NOTIFY, generated columns, RLS, replication chapters
- `asyncpg` driver documentation — pool sizing patterns
- Production patterns from CLAUDE.md (memory thresholds, agent concurrency, backend-only authorization)
- NexusOSINT current architecture (SQLite WAL + write queue from F2)

**Confidence breakdown:**
- HIGH: JSONB, UUID, MVCC writes, CHECK vs ENUM, RLS scope, backup strategy, postgresql.conf tuning (all from official docs and well-established patterns)
- HIGH: Quantified write latency comparison (basic queueing theory + standard pg/sqlite benchmarks)
- MEDIUM: Specific RAM numbers per connection — varies with `work_mem` and query complexity; budget headroom calculation is conservative

---
*PostgreSQL feature research for NexusOSINT v4.2 migration*
*Researched: 2026-05-07*
