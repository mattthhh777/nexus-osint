# Codex Review — Opus Decision Plan

**Date**: 2026-05-12
**Branch**: master
**Scope**: 29 commits from `9486a31` (last Claude-supervised) to `0cded98` (HEAD)
**Diff**: +9459 / −1829 across 117 files
**Author of changes**: external Codex agent, no supervision
**Reviewer status**: 3 parallel reviewers (python / security / database) produced punch list

---

## 1. Context for Opus

Codex executed the entire SQLite → Postgres migration (Phases 17–25), added Redis cache, removed Maigret runtime, hardened admin UI under CSP, fixed blank auth fallback, and rotated admin password handling. No Claude co-author present on any commit after `9486a31`.

Sonnet review surfaced **5 CRIT + 12 HIGH + 14 MED + 5 LOW** findings (see Sonnet consolidated report in this session). Mechanical fixes are listed in §3 below — Sonnet executes those once Opus signs off on the §2 arch decisions.

CLAUDE.md non-negotiables currently violated:
- Pydantic on all input (admin_create_user takes raw dict)
- No PII in log without hash (disc_id, query targets in 10+ sites)
- JWT only via httpOnly cookie (Bearer fallback still wired)
- CSP without `unsafe-inline` (functional fail: style attributes in innerHTML)
- Rate limit per-user (Bearer bypass routes to IP key)
- No `create_task` outside registry (watchdog)
- No `except Exception` generic (watchdog has documented exception — Opus must accept or refactor)

---

## 2. Arch Decisions Required (Opus calls)

### D1 — Blacklist purge lifecycle
**Problem**: `deps.py:151` runs `DELETE FROM token_blacklist WHERE exp < now()` inline on every authenticated request. Adds DB write to every auth hot path; 503 cascade if Postgres slow.

**Options**:
- **A**: Move to orchestrator scheduled task, run every 60s. Simple, predictable. Adds one more registered task.
- **B**: Lazy on auth — only purge if `random() < 0.01` (1% sample). Zero new infra. Statistical guarantee weak.
- **C**: Partition `token_blacklist` by day, DROP old partitions via cron. Most scalable, biggest infra change.

**Recommendation**: A. Aligns with CLAUDE.md `TaskGroup + registry` discipline.

**Open question for Opus**: confirm A and pick interval (60s? 5min?). Define behavior if scheduler stops (alert? hard fail?).

---

### D2 — Alembic concurrent-startup lock
**Problem**: `entrypoint.sh:5` runs `alembic upgrade head` with no advisory lock. Two containers starting in parallel (restart storm, rolling deploy) race. `alembic_version` table gets corrupt PK or duplicate apply.

**Options**:
- **A**: `pg_advisory_lock(<fixed_id>)` in shell wrapper before `alembic upgrade head`, unlock after.
- **B**: Run migrations in a one-shot init container (compose `depends_on` with init pattern). Cleaner separation, more compose complexity.
- **C**: Move migrations out of entrypoint entirely — manual `alembic upgrade head` via SSH at deploy time. Smallest blast radius, biggest operational risk if forgotten.

**Recommendation**: A for now (single-node VPS). Document advisory lock ID (suggest `8765432100`) in CLAUDE.md.

**Open question for Opus**: confirm lock-ID convention. Decide failure mode if lock held >N seconds (timeout? fail fast?).

---

### D3 — Alembic DDL ownership
**Problem**: `0001_postgres_baseline.py:116` uses `Table.create(bind, checkfirst=True)` instead of `op.create_table()`. Bypasses Alembic DDL tracking — `downgrade()` calls `op.drop_table()` (asymmetric), and future `alembic revision --autogenerate` sees phantom diffs.

**Options**:
- **A**: Rewrite baseline migration to use `op.create_table()`. Requires drop + re-apply on dev / clean re-cutover. Existing prod data already migrated — needs careful migration squash.
- **B**: New "consolidation" migration that emits no-op DDL but populates Alembic metadata correctly. Keeps prod intact, fixes autogenerate.
- **C**: Accept the debt — document that autogenerate is unreliable, all schema changes must be hand-written. Cheapest, ugliest.

**Recommendation**: B if prod cutover already happened (per commit `d925abb`). Verify prod state before deciding.

**Open question for Opus**: confirm prod cutover state. If clean, A. If data live, B.

---

### D4 — Keyset pagination for `/api/admin/logs`
**Problem**: `admin.py:98` uses `LIMIT $1 OFFSET $2` capped at offset 10000. Postgres scans + discards O(offset) rows every page. `SELECT *` includes JSONB `payload` for discarded rows.

**Options**:
- **A**: Keyset pagination using `(ts, id)` tuple. Stateless, fast. API contract changes — client passes `last_ts` + `last_id` instead of `offset`.
- **B**: Bounded OFFSET (cap at 1000) + remove `payload` from default projection. Cheapest fix, doesn't solve at scale.
- **C**: Cursor-based pagination via server-side state (Redis). Most flexible, most infra.

**Recommendation**: A + remove `payload` from list endpoint, expose `payload` only on detail endpoint `/api/admin/logs/{id}`.

**Open question for Opus**: API breakage acceptable now (pre-launch)? Or ship B as patch + A in v4.3?

---

### D5 — Encryption at rest for pg_dump backups
**Problem**: `scripts/pg_backup.sh` writes plaintext SQL to `/root/backups/`. VPS snapshot or disk seizure exposes all `searches.query`, `ip`, `payload`. GDPR Art. 32 violation.

**Options**:
- **A**: GPG symmetric with passphrase file (`chmod 400`, separate dir). Self-contained, no external KMS.
- **B**: age (modern alternative to GPG). Smaller dep, cleaner UX. New tool on VPS.
- **C**: Push to S3-compatible storage (Hetzner Object Storage) with SSE. Offsite by design, adds network dep.

**Recommendation**: A short-term. Revisit C in v5.0 when offsite backup becomes mandatory.

**Open question for Opus**: passphrase rotation policy? Where does passphrase live (Vault, env, file)?

---

### D6 — `quota_log` structural model
**Problem**: `search_service.py:128` does INSERT + DELETE-trim in two separate transactions. Table grows unbounded on crash between them; DELETE subquery non-deterministic under concurrency.

**Options**:
- **A**: Combine into one `async with db.transaction()`. Minimal change, fixes atomicity, doesn't fix structural append model.
- **B**: Replace append-and-trim with single-row UPSERT (`INSERT ... ON CONFLICT (date_key) DO UPDATE`). Eliminates trim entirely. Schema change required.
- **C**: Keep append model, add daily partitioning + auto-DROP old partitions. Heaviest infra.

**Recommendation**: B. The current append model exists because SQLite couldn't do `ON CONFLICT DO UPDATE` cleanly — that constraint is gone now.

**Open question for Opus**: A as patch + B as Phase 26? Or B directly?

---

### D7 — Watchdog `except Exception` in `api/watchdog.py:123`
**Problem**: Background loop catches `Exception` generically with self-referential comment "documented background-loop guard pattern". CLAUDE.md does not document this allowance. Either CLAUDE.md is incomplete, or the code violates it.

**Options**:
- **A**: Amend CLAUDE.md to add explicit allowance for `# Background-loop guard: catch Exception, log, continue`. Documents the existing pattern, accepts the looseness.
- **B**: Refactor watchdog to catch typed exceptions only (`OSError`, `AttributeError`, `psutil.Error`). Re-raise others. Loop dies on unexpected error → orchestrator restart.
- **C**: Replace watchdog with FastAPI startup task using BackgroundTasks + try/except per-tick with typed catches. Cleanest, biggest refactor.

**Recommendation**: B. Watchdog dying loudly on unknown error is better than silently swallowing it. Container restart policy is the safety net.

**Open question for Opus**: accept loop death on unknown error? Or keep current behavior with A?

---

## 3. Mechanical Fix Queue (Sonnet executes post-Opus signoff)

Order optimized for: security-first, then CLAUDE.md compliance, then perf.

### Wave 1 — Security CRIT (deploy gate)
1. C1 `auth_service.py:122` — `hmac.compare_digest(password, APP_PASSWORD)` + audit if fallback path even reachable post-`_ensure_default_user`. Remove if redundant.
2. C2 `search_service.py:456,471` — `hash(disc_id)` in log, label `"Discord lookup…"` in SSE progress.
3. H8 (10+ sites in `search_service.py`) — replace `str(exc)` / `%s, exc` with `type(exc).__name__` in `logger.error/warning` calls touching httpx errors. Grep: `logger\.(error|warning).*exc`.

### Wave 2 — CLAUDE.md compliance
4. H6 `admin.py:132` — `CreateUserRequest(BaseModel)` in `schemas.py` with `username: str (regex)`, `password: str (8≤len≤128)`, `role: Literal["user","admin"]`. Wire endpoint to schema.
5. H4 `deps.py:196` — strip Bearer branch from `get_current_user`. Verify no legacy client depends on it (grep frontend).
6. H1 `main.py:154` — register watchdog task in `orchestrator._registry["watchdog"]` at startup, pop at shutdown.
7. M1 `schemas.py` — `@field_validator("username","password")` on `LoginRequest` with `len(v) <= 128`.
8. M3/D7 — apply chosen option from D7.

### Wave 3 — Frontend CSP correctness
9. H5a `render.js:683,706` — Discord banner via `el.style.backgroundImage = url('...')` after DOM insert, drop inline `style=`.
10. H5b `admin.js:189` — chart bars via `createElement` + `el.style.height`, drop inline `style=`.
11. M5 `admin.js:351` — sanitize username (strip `\n\r\t`) before `confirm()` template.
12. M6 `admin.py:93,144,176` — regex `r'^[a-zA-Z0-9_.-]{1,64}$'`.

### Wave 4 — DB correctness
13. H2 `search_service.py:147,213` — drop `= None` defaults on `db` and `orch` params.
14. H3 `search_service.py:233` — `asyncio.wait_for(_sentinel_done.wait(), timeout=300)` in `_search_sentinel`.
15. H7 `admin.py:48` — `LIMIT 100` on `per_user` query.
16. H10 — new Alembic migration `0003_rate_limits_unique.py`: `UNIQUE (key, ts)` on `rate_limits`.
17. H11 — same migration or `0004_searches_user_ts_index.py`: `CREATE INDEX idx_searches_username_ts ON searches (username, ts DESC)`.
18. C3 — apply chosen option from D1.
19. C4 — apply chosen option from D2.
20. C5 `port_searches.py:139` — `timeout=30` on `asyncpg.connect`, swap `TRUNCATE` for `INSERT ... ON CONFLICT (id) DO NOTHING` (or natural key TBD).
21. H12 — apply chosen option from D4.
22. M7 `quota_log` — apply chosen option from D6.

### Wave 5 — Infra / ops
23. H9 — apply chosen option from D3.
24. M10 — apply chosen option from D5.
25. M11 `pg_restore_drill.sh` — add per-table counts (token_blacklist, rate_limits, quota_log) + write probe.
26. MED-2 `entrypoint.sh` — Alembic as non-root (su to appuser or USER directive).
27. MED-3 `0002_enable_pg_stat_statements.py` — runtime assertion that extension loaded.
28. MED-4 `nginx.conf:115` — append `; preload` to HSTS, submit hstspreload.org.
29. MED-7 `alembic.ini:6` — placeholder DSN, document override.
30. MED-8 `docker-compose.yml:104` — remove `mem_limit`, keep only `deploy.resources.limits.memory`.

### Wave 6 — LOW cluster (post-deploy ok)
- `db.py:196` aliases removed
- `_seen_breach_extra_keys` cap at 1000
- `_users_cache` test teardown
- `users.json` chmod 600
- `port_searches.py:107` check_same_thread=False
- `Transaction.fetch_stream` added

---

## 4. Risk Register (state to Opus)

| Risk | Severity | Mitigation timing |
|---|---|---|
| Plaintext password comparison reachable on first boot | CRIT | Wave 1 (C1) |
| Discord IDs in production logs | CRIT (GDPR) | Wave 1 (C2) |
| Auth latency spike under DB pressure | CRIT (DoS) | Wave 4 (C3 via D1) |
| Concurrent startup migration race | CRIT (data integrity) | Wave 4 (C4 via D2) |
| Port script lock-hangs migration window | CRIT (RTO) | Wave 4 (C5) |
| CSP breakage on banner + chart | HIGH (UX, regression risk) | Wave 3 |
| Bearer fallback widens attack surface | HIGH | Wave 2 (H4) |
| Plaintext backups on disk | HIGH (GDPR) | Wave 5 (D5) |
| Alembic autogenerate phantom diffs | MED (operational) | Wave 5 (D3) |

---

## 5. Opus Signoff (2026-05-12)

**Reviewer**: Opus 4.7 session. Prod cutover state verified via `.planning/cutovers/phase24-20260510T210438Z.md` — Postgres live, 19 rows ported, asyncpg pool size 2, public `/health` healthy. All seven decisions below are locked; Sonnet executes §3 strictly in this shape unless a finding contradicts the rationale (in which case: stop, escalate).

---

### [x] D1 — Blacklist purge lifecycle → **A** (orchestrator scheduled task, **60s interval**)

**Why A**: aligned with CLAUDE.md `TaskGroup + registry` discipline. Removes DB write from every auth hot path (which currently 503-cascades if Postgres slow — finding C3). B (1% sample) is statistical hand-waving for a security primitive. C (partitioning) is over-engineering for a table that holds at most ~N*TTL rows on a single-node VPS with ~20 max connections.

**Why 60s, not 5min**: blacklist exists to invalidate compromised tokens fast. Stale rows past `exp` carry no security risk (auth path already filters by `exp > now()`), so purge cadence is a storage hygiene knob, not a security knob. 60s keeps the table tiny and predictable for `pg_stat_statements`; 5min lets it grow by ~5x with no real benefit. Cost: one indexed DELETE per minute, negligible.

**Failure mode if scheduler stops**: log `WARNING` once per minute (rate-limited via `loguru.opt(once=True)` or a module-level flag), expose `blacklist_purge_last_success_ts` in `/health`, do **not** hard-fail. Blacklist still functions correctly (auth path filters by `exp`); only cleanup degrades. Container restart fixes it.

**Wire-up requirements for Sonnet**:
- Register as `orchestrator._registry["blacklist_purge"]` at FastAPI startup, cancel at shutdown.
- Reuse the watchdog's `try/except CancelledError → raise` + log-and-continue pattern (post D7 amendment).
- Single SQL: `DELETE FROM token_blacklist WHERE exp < now() - interval '5 minutes'` (5min grace so a token rejected at the edge of its TTL doesn't race a purge).
- Remove the inline `DELETE` from `deps.py:151`.

---

### [x] D2 — Alembic concurrent-startup lock → **A** (`pg_advisory_lock` in shell wrapper, lock ID `8765432100`)

**Why A**: single-node VPS with one compose stack. B (init container) doubles compose surface area for a problem that exists once per deploy. C (manual SSH) is a footgun — every "forgot to migrate" incident is a prod outage.

**Lock ID convention**: `8765432100` (decimal, fits in `bigint`). Document in `CLAUDE.md` under "References Quick". Rationale for namespacing: this is the only advisory lock in the system right now; if a second one is ever needed, allocate `8765432101..N` and table it in CLAUDE.md.

**Failure mode if lock held >30s**: fail fast — `pg_advisory_lock` blocks indefinitely by default, but the wrapper should use `pg_try_advisory_lock` in a 30s polling loop, then exit non-zero with a clear log line. Container exits, compose's `restart: unless-stopped` retries. If the holder is wedged, operator sees the loop in `docker logs` immediately.

**Implementation shape for Sonnet** (`entrypoint.sh`):
```bash
LOCK_ID=8765432100
TIMEOUT_S=30
START=$(date +%s)
while true; do
  GOT=$(psql "$DATABASE_URL" -tAc "SELECT pg_try_advisory_lock($LOCK_ID)")
  [ "$GOT" = "t" ] && break
  [ $(($(date +%s) - START)) -ge $TIMEOUT_S ] && { echo "alembic lock timeout"; exit 1; }
  sleep 1
done
alembic upgrade head
RC=$?
psql "$DATABASE_URL" -tAc "SELECT pg_advisory_unlock($LOCK_ID)" >/dev/null
exit $RC
```
Use `psql` from the runtime image. If `postgresql-client` is not already installed in the runtime stage, add it and re-verify `docker images nexus < 250MB` after the add.

---

### [x] D3 — Alembic DDL ownership → **B (refined: wire `target_metadata` properly, do NOT rewrite baseline)**

**Prod state verified**: cutover ran `2026-05-10T21:04:38Z`, 19 rows in `searches` migrated via `port_searches.py`, baseline migration `0001` was applied successfully to live Postgres. Dropping and recreating tables is **not** an option.

**Root cause refined**: the phantom-diff problem is not that `Table.create(bind, checkfirst=True)` ran — that's a runtime concern, not an autogenerate concern. Autogenerate compares `migrations/env.py:target_metadata` against the live DB schema. The local `metadata = sa.MetaData()` in `0001_postgres_baseline.py:100` is **not** what env.py points at — autogenerate sees an empty/stub `target_metadata`, compares against a fully-populated live DB, and reports every existing table as a phantom diff.

**Fix (Sonnet, Wave 5)**:
1. Create `migrations/models.py` defining a single `MetaData()` and all four tables (`searches`, `token_blacklist`, `rate_limits`, `quota_log`) with their indexes — exact copy of the Column definitions currently in `0001_postgres_baseline.py`, just hoisted to a stable module.
2. In `migrations/env.py`, set `target_metadata = migrations.models.metadata`.
3. Leave `0001_postgres_baseline.py` **untouched** on prod. It already ran, schema is correct, `alembic_version` is in good shape.
4. Verify with `alembic check` — should report no diffs against the live DB.
5. Future migrations from autogenerate now work correctly.

**Downgrade asymmetry**: leave as-is. Downgrade of the baseline is theoretical (you don't roll back a baseline in production); the asymmetry isn't a runtime risk, only an aesthetic one.

**Why not full rewrite (option A as originally framed)**: requires drop + re-apply on prod, which means a second cutover window, second port script run, second smoke test cycle, and another row-count audit. Cost vastly exceeds the benefit of "cleaner migration source". The metadata-wiring fix solves the actual user-visible problem (autogenerate works) without touching prod.

---

### [x] D4 — Keyset pagination for `/api/admin/logs` → **A directly** (no B-then-A bridge)

**Why A now**: pre-launch, no external clients depend on offset semantics. The `/api/admin/logs` endpoint is consumed only by `static/admin.js`, which Sonnet will update in the same wave. Shipping B (capped offset) first then A in v4.3 means two API contract changes back-to-back and two admin.js touchpoints. Not worth it.

**API shape**:
- `GET /api/admin/logs?limit=50&before_ts=<iso8601>&before_id=<uuid>`
  - First page: omit `before_*`.
  - Subsequent: pass the `(ts, id)` of the last row from previous page.
- Response: `{"items": [...], "next": {"before_ts": "...", "before_id": "..."} | null}`.
- `payload` field **removed** from list items (return only `id`, `ts`, `username`, `target_kind`, `target_hash`, `status`).
- `GET /api/admin/logs/{id}` — new detail endpoint, returns full row with `payload`.

**SQL shape** (keyset, deterministic on `(ts DESC, id DESC)`):
```sql
SELECT id, ts, username, target_kind, target_hash, status
FROM searches
WHERE ($1::timestamptz IS NULL OR (ts, id) < ($1, $2))
ORDER BY ts DESC, id DESC
LIMIT $3;
```
Requires an index supporting `(ts DESC, id DESC)`. Sonnet decides: extend H11's `idx_searches_username_ts` to cover this, add a separate `idx_searches_ts_id_desc`, or merge both into one composite. Index choice goes in the same migration as H11.

**`limit` validation**: Pydantic `Field(ge=1, le=200)`. Hard cap at 200 prevents memory blowup from `?limit=999999`.

**admin.js**: replace `?offset=N` with cursor state in a `let cursor = null;` closure, update "Load more" to pass `cursor`, stop when `next === null`.

---

### [x] D5 — Encryption at rest for pg_dump backups → **A** (GPG symmetric, file-based passphrase)

**Why A over B (age)**: GPG ships in `gnupg` on Debian slim — already a transitive dep of several base utilities. age is cleaner UX but adds a runtime dep and a tool the operator may not have on a recovery laptop. GPG decrypt works from any unix in a pinch.

**Why not C (S3/Hetzner Object Storage)**: offsite backup is the right v5.0 move (single-VPS = single point of failure for backups too), but it crosses a network boundary, requires API credentials with their own rotation discipline, and adds an external dependency for the daily backup hot path. Not a v4.x change.

**Passphrase storage**: `/root/.config/nexus/backup.key` — single-line passphrase, `chmod 400`, `chown root:root`, **never** in env, **never** in git, **never** in compose. Backup script reads it via `--passphrase-file`. The file lives outside `/root/nexus-osint/` so it's not in any image build context.

**Rotation policy**: yearly (set a calendar reminder; document in `CLAUDE.md` under DEPLOY). Rotation procedure:
1. Generate new passphrase, write to `/root/.config/nexus/backup.key.new`.
2. Re-encrypt last 7 backups with new key (verify decrypt with old key first, then re-encrypt).
3. `mv backup.key.new backup.key`, secure delete old (`shred`).
4. Verify next nightly backup decrypts.

**Restore drill**: `pg_restore_drill.sh` (covered in M11) decrypts a recent backup into an ephemeral container, runs row counts and a write probe, drops the ephemeral container. Run weekly via cron — silent rot on backup encryption is the failure mode that matters.

**Implementation shape** (`scripts/pg_backup.sh`, replace plaintext write):
```bash
pg_dump "$DATABASE_URL" --format=custom \
  | gpg --symmetric --cipher-algo AES256 \
        --passphrase-file /root/.config/nexus/backup.key \
        --batch --no-tty \
        --output "/root/backups/nexus-$(date +%Y%m%dT%H%M%SZ).sql.gpg"
```

---

### [x] D6 — `quota_log` structural model → **A in Wave 4 (atomicity patch) + B as Phase 26 (structural fix)**

**Why both**: A is a 5-line change that fixes the **current correctness bug** (INSERT + DELETE-trim in separate transactions = table grows unbounded on crash between them). It ships in the same wave as the rest of the DB hardening, no schema change, no migration. B is the right long-term model but it's a schema migration that deserves its own phase, its own STATE.md entry, and its own rollback plan.

**Wave 4 (A) — atomicity**: wrap `search_service.py:128` INSERT + trim DELETE in a single `async with conn.transaction():`. Trim DELETE: make deterministic by ordering — `DELETE FROM quota_log WHERE id IN (SELECT id FROM quota_log ORDER BY ts ASC OFFSET 1000)`. Without an `ORDER BY` the subquery is non-deterministic under concurrency.

**Phase 26 (B) — UPSERT**: schema migration adds `date_key DATE PRIMARY KEY` (or composite `(date_key, username)` if per-user quota is needed — Sonnet to confirm against current logic). Replace append with `INSERT ... ON CONFLICT (date_key) DO UPDATE SET used_today = quota_log.used_today + 1, ts = EXCLUDED.ts`. Migration backfills `date_key` from existing `ts::date`, dedups by keeping the max row per date, drops the redundant rows.

**Why this split, not B directly**: shipping B in Wave 4 means a schema migration in the same PR as security fixes and DB hardening. Bigger PR = harder review, higher revert blast radius. Keep migrations on their own phase boundary.

**Phase 26 acceptance criteria** (for the milestone roadmap):
- Schema migration applied, backfill verified by row-count delta vs. pre-migration row count.
- Quota logic uses UPSERT in the single hot path.
- DELETE-trim code removed.
- Smoke: 100 concurrent searches don't produce duplicate `date_key` rows.

---

### [x] D7 — Watchdog `except Exception` → **A** (amend CLAUDE.md to document the background-loop guard pattern; keep watchdog code as-is)

**Why A, not B (refactor to typed catches)**: the §2 recommendation for B claims "container restart policy is the safety net" — that's **factually wrong** for this code. The watchdog is an `asyncio` task launched once at FastAPI startup. If it raises an unhandled exception, the task dies, the container keeps running, FastAPI keeps serving — the watchdog is silently gone. There's no restart policy that catches a dead task inside a healthy container. The only safety net for B would be a supervisor task that monitors the watchdog and restarts it, which is itself a background loop with the exact same problem one level up. Infinite regress.

**Why A, not C (FastAPI BackgroundTasks rewrite)**: BackgroundTasks is for per-request fire-and-forget work, not for long-running supervisor loops. Wrong tool. A TaskGroup-managed background task is the right shape, which is what we already have.

**The actual rule (to amend into CLAUDE.md)**:

> **Background-loop guard exception**: a long-running supervisor task (watchdog, scheduler, queue consumer) may catch `Exception` in its outermost per-tick `try/except` **if and only if**:
> 1. `asyncio.CancelledError` is caught separately and re-raised before the `Exception` handler.
> 2. The exception is logged via `logger.exception(...)` with full traceback, never silently swallowed.
> 3. The handler does nothing other than log and continue — no state mutation, no recovery logic, no retry counter.
> 4. The task is registered in `orchestrator._registry` so it's auditable via `/health/agents` (post-H1 fix).
>
> Rationale: a supervisor crash on an unexpected exception type causes **silent loss of supervision**, which is worse than a logged-and-continued tick. The same logic applies to `orchestrator._guarded()` and any future scheduled task (e.g., D1 blacklist purge).

**Sonnet's task in Wave 2 (M3/D7)**: append the above paragraph to `CLAUDE.md` under "PADRÃO DE EXCEPTION HANDLING" as a sub-section. The `noqa: BLE001` comment on `watchdog.py:123` stays. The D1 blacklist purge task (Wave 4) reuses the same pattern.

---

### Cross-cutting notes for Sonnet

1. **Wave ordering**: Wave 1 (security CRIT) ships first as its own PR, deploys to prod immediately. Waves 2–6 follow in order. **Do not** batch waves into one PR — the point of the wave structure is small, atomic, revertible deploys.
2. **CLAUDE.md edits**: D2 lock ID, D5 backup procedure + rotation policy, D7 background-loop guard rule all land in **one** documentation commit at the end of Wave 5 (`docs(claude.md): formalize D2/D5/D7 conventions`). Do not edit CLAUDE.md piecemeal across waves.
3. **Per-wave gate**: each wave's PR must include — passing tests, `/health` smoke against prod-like compose stack, no new warnings in `docker logs`, atomic per-item commits with conventional-commit messages mapping `C{n}` / `H{n}` / `M{n}` to commit subject.
4. **Phase 26 prerequisite**: D4 keyset and D6 UPSERT both need their migrations co-designed with the existing 0001 baseline. Before writing migration 0003 or 0004, run `alembic check` to confirm D3's metadata wiring works.
5. **If Sonnet finds a contradiction**: stop. Open a comment block in this file under a new `## 7. Sonnet escalations` section, describe the contradiction, ping Opus session. Do not improvise on D1–D7.

After signoff: Sonnet picks up §3 in order. Each wave is one branch, one PR, atomic commits per item.

---

## 6. Out of scope for this round

- Phase 18 Redis cache review (deferred — works, not blocking)
- Planning artifacts (`.planning/phases/17-25/`) — documentation, not runtime
- Migration script `port_searches.py` testing on real prod snapshot (separate exercise)
- v4.3 milestone scoping
