---
phase: 24-postgres-cutover
plan: 01
requirements-completed: [DBM-38, DBM-39, DBM-40, DBM-41, DBM-42, DBM-43, DBM-44, DBM-45, DBM-46]
completed: 2026-05-10
duration: "maintenance window"
key-files:
  modified:
    - docker-compose.yml
    - scripts/port_searches.py
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
  created:
    - .planning/cutovers/phase24-20260510T210438Z.md
    - .planning/phases/24-postgres-cutover/24-01-SUMMARY.md
    - .planning/phases/24-postgres-cutover/24-VERIFICATION.md
---

# Phase 24 Plan 01: Hetzner PostgreSQL Cutover Summary

## Result

Phase 24 cutover is complete. Production NexusOSINT now boots with
`DATABASE_URL=postgresql+asyncpg://...`, `/health` reports an active Postgres
pool, and the `searches` table was ported from the SQLite snapshot with row-count
parity.

## What Changed

- `docker-compose.yml`
  - Fixed the multiline `uvicorn` command so `--host 0.0.0.0` is passed to the
    process. Without this fix, Uvicorn bound to `127.0.0.1` and nginx could not
    reach the app.
- `scripts/port_searches.py`
  - Allows `DATABASE_URL` from env when `--database-url` is omitted, avoiding
    secret exposure in shell history/output during cutover.
- VPS `.env`
  - Added `DATABASE_URL` using the existing Postgres secret.
  - Toggled `READ_ONLY_MODE=true` during the write freeze, then restored
    `READ_ONLY_MODE=false`.

## Cutover Evidence

- SQLite snapshot: `/app/data/audit.db.pre-pg-20260510T210438Z`, mode `0400`.
- Pre-cutover image tag: `nexus-osint-nexus:pre-pg-backup-20260510T210438Z`.
- Alembic: `upgrade head` completed against Postgres.
- Port script: `PORT_SEARCHES_OK rows=19 elapsed_s=0.060`.
- Postgres row count: `select count(1) from searches` -> `19`.
- `/health`: `status=healthy`, `db.started=true`, `db.size=2`, `db.idle_size=2`,
  `active_tasks=0`, `rss_mb=77.2`.
- Public HTTPS `/health`: healthy.
- Public `/`: HTTP `200`.
- Public `/admin`: HTTP `403` without admin cookie, expected.
- Docker stats after cutover:
  - `nexus-osint 58.13MiB / 2.441GiB`
  - `nexus-postgres 36.17MiB / 768MiB`
  - `nexus-redis 3.297MiB`

## Requirement Status

- DBM-38: complete. Snapshot, image tag, and git SHA captured in the cutover runbook.
- DBM-39: complete. `READ_ONLY_MODE=true` returned `503` for write requests.
- DBM-40: complete. `/health` reported `active_tasks=0` before final unlock.
- DBM-41: complete. `port_searches.py` asserted SQLite/Postgres parity at 19 rows.
- DBM-42: not applicable. Schema uses UUID primary keys and no serial sequences.
- DBM-43: complete. `DATABASE_URL` flipped and `docker compose up -d` succeeded.
- DBM-44: complete. Health, dashboard, admin path, and DB row-count smoke passed.
- DBM-45: complete. Read-only mode disabled; SQLite snapshot remains read-only.
- DBM-46: accepted with caveat. The user explicitly approved proceeding despite no
  discovered staging rollback proof and dirty VPS worktree.

## Deviations from Plan

- Remote VPS lacked `scripts/`, `migrations/`, and `alembic.ini`; these non-secret
  migration assets were synced before cutover.
- Syncing current `api/` code before rebuilding briefly caused app startup failure
  because the old image lacked `asyncpg`. Rebuilding `nexus` from current
  `requirements.txt` resolved it.
- Compose command formatting caused Uvicorn to ignore network args and bind
  `127.0.0.1`. Fixed before public smoke and preserved in repo.

## Remaining Risks

- Remote worktree remains dirty and should be reconciled/committed before the next
  deploy.
- Docker image size is still above the historical target; defer optimization to a
  dedicated image-size cleanup, not the cutover window.

