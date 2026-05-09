# Phase 17: v4.2 Pre-Migration Audit & DB Abstraction Layer — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Source:** Approved plan (~/.claude/plans/drifting-mixing-engelbart.md, 2026-05-06)

<domain>
## Phase Boundary

Foundational phase of milestone v4.2 (SQLite → PostgreSQL migration). LOW risk — app stays on SQLite at end of phase. Three contained objectives:

1. **Inventory** every raw SQL statement in codebase → `SQL_INVENTORY.md`.
2. **Audit** SQLite-dialect violations that break in PG (`AUTOINCREMENT`, `INSERT OR REPLACE`, `datetime(`, `strftime(`, `rowid`, `?` placeholders outside abstraction). Build `?`→`$N` placeholder map → `PLACEHOLDER_MAP.md`.
3. **Abstraction layer** `db.fetch_one / fetch_all / execute / transaction` wrapping current aiosqlite. Refactor all call sites. Phase 21 driver swap touches only `api/db.py`.

Requirements covered: **DBM-01, DBM-02, DBM-03, DBM-04**.

</domain>

<decisions>
## Implementation Decisions (LOCKED — from approved plan)

### Sequencing
- Sequential: 17-01 → 17-02 → 17-03. Atomic commit per sub-plan.
- Branch: `v4.2/p17-audit-abstraction` from `master`.

### 17-01 — Inventory & Audit (DBM-01, DBM-03, DBM-04)
- Outputs:
  - `.planning/phases/17-.../SQL_INVENTORY.md` — columns: `File:Line | Statement | Type | Table | Placeholders | Migration notes`.
  - `.planning/phases/17-.../PLACEHOLDER_MAP.md` — columns: `File:Line | SQL with ? | Target SQL with $N | Refactor location`.
- Canonical greps:
  ```
  grep -rnE "AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(|\browid\b|\.fetchone\(|\.fetchall\(" api/ scripts/ tests/
  grep -rnE "(SELECT |INSERT |UPDATE |DELETE |CREATE |DROP |ALTER )" api/ scripts/
  ```
- Mitigations:
  - `AUTOINCREMENT` in `api/db.py:131` (DDL): documented only — handled in Phase 19 (UUID-all schema). Do NOT touch.
  - `rowid` in `api/services/search_service.py:56-57` (`DELETE FROM quota_log WHERE rowid NOT IN ...`): replace with `id` (PK explicit). Equivalent semantics; works in PG (BIGSERIAL).
- DoD:
  - DBM-01: post-fix canonical grep returns only `api/db.py:131`.
  - DBM-03: inventory covers 100% of statements.
  - DBM-04: placeholder map covers 100% of `?` sites.
- Commit: `docs(v4.2): phase 17-01 SQL inventory + placeholder map + rowid fix`

### 17-02 — Abstraction Layer Expansion (DBM-02 base)
Single file edit: `api/db.py`.

Additions:
1. **Canonical aliases** (no rename — preserve callers):
   - `fetch_one = read_one`
   - `fetch_all = read_all`
   - `fetch_stream = read_stream`
   - `execute = write_await` (write blocking, errors propagate)
   - `execute_nowait = write` (fire-and-forget)
2. **`transaction()` async context manager**:
   ```python
   @asynccontextmanager
   async def transaction(self) -> AsyncIterator["Transaction"]:
       async with self._tx_lock:        # serialize against _writer_loop
           await self._conn.execute("BEGIN IMMEDIATE")
           try:
               yield Transaction(self._conn)
               await self._conn.commit()
           except Exception:
               await self._conn.rollback()
               raise
   ```
3. **`Transaction`** facade — light wrapper exposing `fetch_one/fetch_all/execute` directly on the connection. In Phase 21 becomes `pool.acquire() + conn.transaction()`.
4. **`_tx_lock: asyncio.Lock`** — acquired by `transaction()`. Writer loop does NOT acquire (continues using connection after lock release). Rationale: SQLite WAL serializes writes on single connection; lock prevents writer executing statements between BEGIN and COMMIT of TX. Caller-side `wait_for(timeout=10s)` for diagnostics.
5. **`DatabaseError(Exception)`** — wraps `aiosqlite.Error`. All public methods catch and re-raise as `DatabaseError`.

Tests in `tests/test_db_abstraction.py`:
- `fetch_one` returns `dict | None`.
- `fetch_all` returns `list[dict]`.
- Failed `execute` raises `DatabaseError`.
- `transaction()` commits on success, rolls back on exception.
- TX + parallel write: write outside completes after `__aexit__`.

DoD:
- New methods tested.
- No existing test breaks.
- `pytest -q` green.

Commit: `feat(db): add fetch_*/execute/transaction abstraction + DatabaseError`

### 17-03 — Call-Site Refactor + aiosqlite Containment (DBM-02 closure)

Goal: **no module outside `api/db.py` imports or references `aiosqlite`.**

| File | Change |
|------|--------|
| `api/deps.py` | drop `import aiosqlite`; `except (aiosqlite.Error, ...)` → `except (DatabaseError, OSError, ValueError, RuntimeError)` |
| `api/services/search_service.py` | drop `import aiosqlite`; `except (httpx.HTTPError, aiosqlite.Error, ...)` → `except (httpx.HTTPError, DatabaseError, ...)`; rowid fix from 17-01 already applied |
| `api/services/auth_service.py` | (optional) `db.write` → `db.execute_nowait` for style consistency |
| `api/routes/admin.py` | drop `import aiosqlite`; `except aiosqlite.OperationalError` → `except DatabaseError` |
| `api/main.py` | remove `import aiosqlite` line 42 if unused; update comment line 8 |

Verification:
```bash
grep -rn "aiosqlite" api/ --include="*.py"   # expected: only api/db.py
pytest -q
uvicorn api.main:app &  # smoke /health + /admin/dashboard
```

DoD:
- Only `api/db.py` imports `aiosqlite`.
- 17-01 audit re-run: identical result.
- Test suite green.
- Smoke endpoints OK.

Commit: `refactor(v4.2): contain aiosqlite to api/db.py + use DatabaseError at call sites`

### Risks (regra 5 — re-enunciated)
- **R-17.1** TX lock vs writer SQLite contention may mask deadlock. Mitigation: `wait_for(timeout=10s)` + log; `PRAGMA busy_timeout=5000` already active. In Phase 21 (asyncpg) lock becomes no-op.
- **R-17.2** Aliases drifting from `read_*` silently in Phase 21. Mitigation: header in `db.py` documents Postgres target contract; smoke test asserts return type.
- **R-17.3** rowid fix alters `quota_log` DELETE. Mitigation: use `id` (PK), equivalent semantics; new test "200 inserts → exactly 100 newest remain".

### Claude's Discretion
- Test fixture details (`tests/conftest.py` reuse vs new fixture).
- Internal naming for `Transaction` helper class methods.
- Log level / message format for tx-lock timeout.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project rules
- `CLAUDE.md` — exception handling per layer, SQLite WAL + asyncio.Queue contract, no `except Exception` generic, no `.fetchall()` on >100 rows.

### Milestone v4.2 research (locked decisions)
- `.planning/research/SUMMARY.md` — 8-phase synthesis; tuning parameters resolved.
- `.planning/research/STACK.md` — driver/migration tooling decisions (asyncpg + Alembic async).
- `.planning/research/ARCHITECTURE.md` — repository layer pattern, transaction semantics target.
- `.planning/research/PITFALLS.md` — 12 failure modes; Pitfall 1 (dialect drift), Pitfall 4 (asyncpg API differs) directly motivate this phase.
- `.planning/research/FEATURES.md` — PG features adopted (JSONB, GIN, TIMESTAMPTZ, UUID).

### Phase scope
- `.planning/ROADMAP.md` § Phase 17 — goal + deliverable + avoidance list.
- `.planning/REQUIREMENTS.md` § DBM-01..04 — locked acceptance criteria.

### Existing implementation
- `api/db.py` — current `DatabaseManager` (read/read_one/read_all/read_stream/write/write_await + writer loop).
- `api/deps.py:113`, `api/services/search_service.py:355`, `api/routes/admin.py:69,100` — direct `aiosqlite` references (except clauses only).
- `api/services/search_service.py:56-57` — rowid violation site.

</canonical_refs>

<specifics>
## Specific Ideas

### Test "200 inserts → 100 newest remain" (R-17.3 mitigation)
- Insert 200 quota_log rows with monotonically increasing timestamps.
- Run DELETE statement (post-fix using `id`).
- Assert exactly 100 rows remain.
- Assert `min(id)` of remaining > `max(id)` of deleted.

### TX + parallel write test (17-02)
- Coroutine A: `async with db.transaction(): await tx.execute("INSERT ...")`; sleep 0.1; commit.
- Coroutine B: while A inside TX, call `db.execute_nowait("INSERT ...")`.
- Assert B's row appears AFTER A's commit (writer loop blocked on lock).

</specifics>

<deferred>
## Deferred Ideas

- AUTOINCREMENT removal (`api/db.py:131`): Phase 19 (UUID-all schema rewrite).
- Actual driver swap (aiosqlite → asyncpg): Phase 21.
- Connection pooling: Phase 21 (asyncpg native pool).
- Schema migration to PG types (TIMESTAMPTZ, JSONB, BIGSERIAL): Phase 19.

</deferred>

---

*Phase: 17-v4-2-pre-migration-audit-db-abstraction-layer*
*Context locked: 2026-05-07 — approved plan materialized*
