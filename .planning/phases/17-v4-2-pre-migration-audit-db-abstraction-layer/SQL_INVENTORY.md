# SQL_INVENTORY — Phase 17 v4.2 Pre-Migration Audit

**Generated:** 2026-05-08
**Phase:** 17-v4-2-pre-migration-audit-db-abstraction-layer
**Plan:** 17-01 (DBM-03 baseline)
**Source greps (canonical):**
```
grep -rnE "AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(|\browid\b|\.fetchone\(|\.fetchall\(" api/ scripts/ tests/
grep -rnE "(SELECT |INSERT |UPDATE |DELETE |CREATE |DROP |ALTER )" api/ scripts/
```

**Scope:** every raw SQL statement under `api/` and `scripts/`. (`scripts/` is currently empty — no Python files exist there.) Test-only SQL is captured in PLACEHOLDER_MAP.md but is not part of the production inventory.

**Migration tag legend:**
- `DIALECT:AUTOINCREMENT` — SQLite-only PK auto-increment; PG uses `BIGSERIAL` or `GENERATED ALWAYS AS IDENTITY`. **Phase 19** UUID-all schema rewrite handles this. Documented only — DO NOT modify in Phase 17.
- `DIALECT:INSERT_OR_REPLACE` — Not used in this codebase. `INSERT OR IGNORE` IS used (auth_service.py:138) and is also SQLite-specific upsert syntax; PG equivalent is `INSERT ... ON CONFLICT (...) DO NOTHING`. Tagged `DIALECT:INSERT_OR_IGNORE` for symmetry.
- `DIALECT:DATETIME_FN` — `datetime()` / `strftime()` SQL functions. None found. Timestamps are passed as ISO strings from Python (`datetime.now(timezone.utc).isoformat()`); SQL-side date filtering uses `LIKE 'YYYY-MM-DD%'` which is portable.
- `DIALECT:ROWID` — SQLite implicit `rowid` pseudo-column. Found at `api/services/search_service.py:56-57` — fixed in Task 2 of this plan (replaced with `id` PK).
- `DIALECT:LIKE_DATE` — Heuristic date filter `WHERE ts LIKE 'YYYY-MM-DD%'` — works on PG TEXT columns identically; will also work after schema migration to `TIMESTAMPTZ` once query is rewritten in Phase 21 (still functional, less efficient than range predicate).
- `OK` — portable SQL, works in both SQLite and Postgres without rewrite.
- `PRAGMA` — SQLite-only session config. Replaced in Phase 21 by PG equivalents (`SET synchronous_commit`, etc.) inside `api/db.py` only — no behavioral parity needed at call sites.

---

## Inventory Table

| File:Line | Statement | Type | Table | Placeholders | Migration notes |
|-----------|-----------|------|-------|--------------|-----------------|
| api/db.py:76 | `PRAGMA journal_mode=WAL` | PRAGMA | n/a | 0 | `PRAGMA` — SQLite-only; Phase 21 deletes (asyncpg has no equivalent). |
| api/db.py:77 | `PRAGMA synchronous=NORMAL` | PRAGMA | n/a | 0 | `PRAGMA` — SQLite-only; Phase 21 maps to `synchronous_commit` server config. |
| api/db.py:78 | `PRAGMA busy_timeout=5000` | PRAGMA | n/a | 0 | `PRAGMA` — SQLite-only; obsolete under PG MVCC. |
| api/db.py:79 | `PRAGMA cache_size=-8000` | PRAGMA | n/a | 0 | `PRAGMA` — SQLite-only; Phase 21 deletes (PG `shared_buffers` is server-level). |
| api/db.py:80 | `PRAGMA wal_autocheckpoint=100` | PRAGMA | n/a | 0 | `PRAGMA` — SQLite-only; obsolete (no WAL in PG sense). |
| api/db.py:130 | `CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, username TEXT NOT NULL, ip TEXT, query TEXT, ...)` | DDL/CREATE | searches | 0 | **`DIALECT:AUTOINCREMENT`** at line 131 — Phase 19 (UUID-all schema rewrite). DO NOT MODIFY in Phase 17 per CONTEXT.md `<deferred>`. Also: `INTEGER` for boolean `success` → `BOOLEAN` in Phase 19 (Pitfall 3). |
| api/db.py:147 | `CREATE INDEX IF NOT EXISTS idx_ts ON searches(ts)` | DDL/CREATE | searches | 0 | `OK` — portable. Phase 19 may rebuild for `TIMESTAMPTZ` column. |
| api/db.py:150 | `CREATE INDEX IF NOT EXISTS idx_user ON searches(username)` | DDL/CREATE | searches | 0 | `OK` — portable. |
| api/db.py:155 | `CREATE TABLE IF NOT EXISTS token_blacklist (jti TEXT PRIMARY KEY, exp INTEGER NOT NULL)` | DDL/CREATE | token_blacklist | 0 | `OK` syntactically; table dropped greenfield in Phase 19 (REQUIREMENTS.md Locked Decisions). |
| api/db.py:161 | `CREATE INDEX IF NOT EXISTS idx_bl_exp ON token_blacklist(exp)` | DDL/CREATE | token_blacklist | 0 | `OK` — table dropped Phase 19. |
| api/db.py:166 | `CREATE TABLE IF NOT EXISTS rate_limits (key TEXT NOT NULL, ts REAL NOT NULL)` | DDL/CREATE | rate_limits | 0 | `OK` syntactically; `key` column name is unreserved in PG and works unquoted — Phase 19 rebuilds (table dropped greenfield per Locked Decisions). |
| api/db.py:172 | `CREATE INDEX IF NOT EXISTS idx_rate_key ON rate_limits(key)` | DDL/CREATE | rate_limits | 0 | `OK` — table dropped Phase 19. |
| api/db.py:175 | `CREATE INDEX IF NOT EXISTS idx_rate_key_ts ON rate_limits(key, ts)` | DDL/CREATE | rate_limits | 0 | `OK` — table dropped Phase 19. |
| api/db.py:180 | `CREATE TABLE IF NOT EXISTS quota_log (id INTEGER PRIMARY KEY, ts TEXT NOT NULL, used_today INTEGER, left_today INTEGER, daily_limit INTEGER)` | DDL/CREATE | quota_log | 0 | `OK` syntactically. Phase 17 adds explicit `id` and rebuilds legacy SQLite tables that predate it. Phase 19 rewrites to PG-native identity/UUID schema. |
| api/deps.py:99 | `DELETE FROM token_blacklist WHERE exp < ?` | DELETE | token_blacklist | 1 | `OK` — `?` → `$1` mechanical rewrite (PLACEHOLDER_MAP.md). |
| api/deps.py:103 | `SELECT 1 as found FROM token_blacklist WHERE jti = ?` | SELECT | token_blacklist | 1 | `OK` — `?` → `$1` mechanical rewrite. |
| api/services/auth_service.py:138 | `INSERT OR IGNORE INTO token_blacklist (jti, exp) VALUES (?, ?)` | INSERT | token_blacklist | 2 | **`DIALECT:INSERT_OR_IGNORE`** — SQLite-only upsert variant. Phase 21 rewrite: `INSERT INTO token_blacklist (jti, exp) VALUES ($1, $2) ON CONFLICT (jti) DO NOTHING`. |
| api/services/search_service.py:51 | `INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES (?,?,?,?)` | INSERT | quota_log | 4 | `OK` — `?` → `$1..$4` mechanical rewrite. |
| api/services/search_service.py:56-57 | `DELETE FROM quota_log WHERE id NOT IN (SELECT id FROM quota_log ORDER BY ts DESC LIMIT 100)` | DELETE | quota_log | 0 | `OK` — Phase 17 replaced SQLite-only `rowid` with explicit `id` PK and added retention coverage. |
| api/services/search_service.py:77-87 | `INSERT INTO searches (ts, username, ip, query, query_type, mode, modules_run, breach_count, stealer_count, social_count, elapsed_s, success) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)` | INSERT | searches | 12 | `OK` — `?` × 12 → `$1..$12` mechanical rewrite. Note: `success` Python int → BOOLEAN at Phase 19 schema migration. |
| api/routes/admin.py:30 | `SELECT COUNT(*) as cnt FROM searches WHERE ts LIKE ?` | SELECT | searches | 1 | `DIALECT:LIKE_DATE` — `WHERE ts LIKE 'YYYY-MM-DD%'`. Works on TEXT in PG; Phase 19/21 may rewrite to `WHERE ts >= $1 AND ts < $1 + interval '1 day'` for index efficiency once `ts` is `TIMESTAMPTZ`. |
| api/routes/admin.py:34 | `SELECT COUNT(*) as cnt FROM searches` | SELECT | searches | 0 | `OK` — portable. |
| api/routes/admin.py:38-39 | `SELECT query, COUNT(*) as cnt FROM searches WHERE ts LIKE ? GROUP BY query ORDER BY cnt DESC LIMIT 10` | SELECT | searches | 1 | `DIALECT:LIKE_DATE` — same note as admin.py:30. |
| api/routes/admin.py:44-45 | `SELECT username, COUNT(*) as cnt FROM searches WHERE ts LIKE ? GROUP BY username ORDER BY cnt DESC` | SELECT | searches | 1 | `DIALECT:LIKE_DATE` — same note as admin.py:30. |
| api/routes/admin.py:51 | `SELECT used_today, left_today, daily_limit FROM quota_log ORDER BY ts DESC LIMIT 1` | SELECT | quota_log | 0 | `OK` — portable. |
| api/routes/admin.py:88 | `SELECT * FROM searches WHERE username=? ORDER BY ts DESC LIMIT ? OFFSET ?` | SELECT | searches | 3 | `OK` — `?` × 3 → `$1..$3`. |
| api/routes/admin.py:95 | `SELECT * FROM searches ORDER BY ts DESC LIMIT ? OFFSET ?` | SELECT | searches | 2 | `OK` — `?` × 2 → `$1..$2`. |

---

## Summary

- **Total statements inventoried (api/ + scripts/):** 25
  - DDL/CREATE: 9 (1 with `DIALECT:AUTOINCREMENT`)
  - PRAGMA: 5 (all SQLite-only — Phase 21 deletes from `api/db.py`)
  - SELECT: 7 (3 with `DIALECT:LIKE_DATE` heuristic — functional in PG, optimisable later)
  - INSERT: 3 (1 with `DIALECT:INSERT_OR_IGNORE` — Phase 21 rewrite)
  - DELETE: 2 (ROWID violation fixed in Phase 17)
- **Mitigated in Phase 17 (this plan):** ROWID violation (search_service.py:56-57), including explicit `quota_log.id` plus legacy table rebuild.
- **Deferred to Phase 19 (UUID-all schema rewrite):** AUTOINCREMENT (db.py:131), INTEGER-as-bool `success` column.
- **Deferred to Phase 21 (driver swap):** PRAGMA removal, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`, `?` → `$N` placeholders, optional `LIKE 'YYYY-MM-DD%'` → range predicate.

After Task 2 of this plan, the canonical audit grep
```
grep -rnE "AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(|\browid\b" api/ scripts/ tests/
```
returns ONLY `api/db.py:131` (AUTOINCREMENT, deferred to Phase 19). DBM-01 satisfied.

---

*Inventory baseline for v4.2 Phase 17 — DBM-01, DBM-03.*
