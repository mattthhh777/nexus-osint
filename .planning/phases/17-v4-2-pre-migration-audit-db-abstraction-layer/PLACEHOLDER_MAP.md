# PLACEHOLDER_MAP - Phase 17 v4.2

**Generated:** 2026-05-08
**Scope:** raw SQL placeholders under `api/`, plus DB tests that exercise the same abstraction contract.

Phase 21 will perform the mechanical driver swap from SQLite `?` placeholders to asyncpg `$N` placeholders inside the database/repository boundary.

| File:Line | SQL with `?` | Target SQL with `$N` | Refactor location |
|-----------|--------------|----------------------|-------------------|
| api/deps.py:97 | `DELETE FROM token_blacklist WHERE exp < ?` | `DELETE FROM token_blacklist WHERE exp < $1` | `api/db.py` driver adapter or repository rewrite |
| api/deps.py:101 | `SELECT 1 as found FROM token_blacklist WHERE jti = ?` | `SELECT 1 as found FROM token_blacklist WHERE jti = $1` | `api/db.py` driver adapter or repository rewrite |
| api/services/auth_service.py:138 | `INSERT OR IGNORE INTO token_blacklist (jti, exp) VALUES (?, ?)` | `INSERT INTO token_blacklist (jti, exp) VALUES ($1, $2) ON CONFLICT (jti) DO NOTHING` | Phase 21 SQL rewrite |
| api/services/search_service.py:49 | `INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES (?,?,?,?)` | `INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES ($1,$2,$3,$4)` | `api/db.py` driver adapter or repository rewrite |
| api/services/search_service.py:75 | `VALUES (?,?,?,?,?,?,?,?,?,?,?,?)` | `VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)` | `api/db.py` driver adapter or repository rewrite |
| api/routes/admin.py:28 | `SELECT COUNT(*) as cnt FROM searches WHERE ts LIKE ?` | `SELECT COUNT(*) as cnt FROM searches WHERE ts LIKE $1` | Phase 21 may rewrite date predicate |
| api/routes/admin.py:37 | `WHERE ts LIKE ? GROUP BY query` | `WHERE ts LIKE $1 GROUP BY query` | Phase 21 may rewrite date predicate |
| api/routes/admin.py:43 | `WHERE ts LIKE ? GROUP BY username` | `WHERE ts LIKE $1 GROUP BY username` | Phase 21 may rewrite date predicate |
| api/routes/admin.py:87 | `SELECT * FROM searches WHERE username=? ORDER BY ts DESC LIMIT ? OFFSET ?` | `SELECT * FROM searches WHERE username=$1 ORDER BY ts DESC LIMIT $2 OFFSET $3` | `api/db.py` driver adapter or repository rewrite |
| api/routes/admin.py:94 | `SELECT * FROM searches ORDER BY ts DESC LIMIT ? OFFSET ?` | `SELECT * FROM searches ORDER BY ts DESC LIMIT $1 OFFSET $2` | `api/db.py` driver adapter or repository rewrite |
| tests/test_db.py | test SQL using `?` | same ordinal mapping | Test-only; update alongside DB adapter tests |
| tests/test_db_abstraction.py | test SQL using `?` | same ordinal mapping | Test-only; update alongside DB adapter tests |

## Summary

- Production placeholder sites: 10.
- Highest-risk rewrite: `INSERT OR IGNORE`, because it is dialect syntax, not only placeholder syntax.
- Remaining rewrites are mechanical `?` to `$N` in left-to-right parameter order.
