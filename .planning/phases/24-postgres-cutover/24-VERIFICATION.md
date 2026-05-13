---
phase: 24-postgres-cutover
status: passed
verified: 2026-05-10
requirements: [DBM-38, DBM-39, DBM-40, DBM-41, DBM-42, DBM-43, DBM-44, DBM-45, DBM-46]
---

# Phase 24 Verification

## Goal

Execute the documented PostgreSQL production cutover with backups, read-only
guard, data port, and smoke evidence.

## Result

Passed with documented caveats. Production now runs on Postgres with a healthy
asyncpg pool and 19 migrated `searches` rows.

## Must-Haves

| Requirement | Status | Evidence |
|---|---|---|
| DBM-38 | PASS | Snapshot `/app/data/audit.db.pre-pg-20260510T210438Z`; image tag `nexus-osint-nexus:pre-pg-backup-20260510T210438Z`; git SHA in runbook. |
| DBM-39 | PASS | `READ_ONLY_MODE=true` write test returned HTTP `503`. |
| DBM-40 | PASS | Final `/health` reported `active_tasks=0`. |
| DBM-41 | PASS | `PORT_SEARCHES_OK rows=19 elapsed_s=0.060`; Postgres `select count(1)` returned `19`. |
| DBM-42 | N/A | Migration uses UUID primary keys with `gen_random_uuid()`, so no serial sequences remain. |
| DBM-43 | PASS | `.env` has `DATABASE_URL` set; `docker compose up -d --force-recreate nexus` succeeded. |
| DBM-44 | PASS | Public `/health` healthy; `/` returned `200`; `/admin` returned expected unauthenticated `403`; internal `/admin` path served before auth gate. |
| DBM-45 | PASS | `READ_ONLY_MODE=false` after cutover; SQLite snapshot mode `0400`. |
| DBM-46 | PASS WITH CAVEAT | User approved proceeding despite missing staging rollback proof discovered during preflight. |

## Automated Checks

- `python -m pytest tests/test_port_searches.py tests/test_health.py -q --tb=short`
  -> `7 passed, 1 skipped`.
- `python -m pytest tests/test_port_searches.py tests/test_health.py tests/test_orchestrator.py -q --tb=short`
  -> `13 passed, 1 skipped` before VPS mutation.
- Public HTTPS health returned Postgres pool object:
  `db.started=true`, `db.size=2`, `db.idle_size=2`.

## Human Verification

No further human verification required for cutover mechanics. Authenticated search
flow should be manually smoke-tested with a low-cost/no-external-API query before
normal production traffic resumes.

