---
phase: 25-post-migration-tuning-backup-hardening
plan: 01
requirements-completed: [DBM-49, DBM-50, DBM-51, DBM-52, DBM-53]
requirements-deferred: [DBM-47, DBM-48]
completed: 2026-05-11
duration: "same session"
key-files:
  modified:
    - scripts/pg_backup.sh
    - scripts/pg_restore_drill.sh
    - CLAUDE.md
    - .planning/STATE.md
  created:
    - .planning/phases/25-post-migration-tuning-backup-hardening/25-01-SUMMARY.md
---

# Phase 25 Plan 01: Backup Hardening and Postgres Docs Summary

## Result

Phase 25 backup hardening is implemented and validated on the Hetzner VPS. A
real `pg_dump` backup completed, a restore drill restored that backup into a
temporary database and counted the `searches` table, and cron now runs backups
daily at 03:00 with 7-day retention.

DBM-47 and DBM-48 are time-gated. The production cutover completed on
2026-05-10, so one-week traffic review cannot be honestly completed before
2026-05-17. No speculative indexes or autovacuum overrides were added.

## What Changed

- `scripts/pg_backup.sh`
  - Repaired NUL-byte corruption in the local file.
  - Adds a lock directory so overlapping backup runs do not compete.
  - Writes through temporary files, validates gzip integrity, then atomically
    moves the final `.sql.gz` into place.
  - Uses `pg_dump --no-owner --no-privileges --clean --if-exists`.
  - Keeps backup files mode `0600` and prunes `nexusosint-*.sql.gz` after 7 days.
- `scripts/pg_restore_drill.sh`
  - Validates backup readability and gzip integrity before restore.
  - Validates the drill database identifier before interpolating it into SQL.
  - Drops the drill database on exit via cleanup trap.
- `CLAUDE.md`
  - Replaced obsolete SQLite/WAL/`asyncio.Queue` runtime guidance with the
    current PostgreSQL/asyncpg/Alembic architecture.
  - Updated test guidance and quick-reference rules to avoid reintroducing
    `aiosqlite` in runtime work.
- VPS cron
  - Installed:
    `0 3 * * * cd /home/deploy/nexus-osint && PG_BACKUP_DIR=/home/deploy/nexus-osint/backups/postgres /bin/sh scripts/pg_backup.sh >> /home/deploy/nexus-osint/logs/pg_backup.log 2>&1`

## Verification

- Commit:
  - `65af8e9` — `feat(25): harden postgres backup operations`
- Targeted tests: `python -m pytest tests/test_port_searches.py tests/test_db.py -q --tb=short`
  -> `5 passed, 7 skipped`.
- Local script line endings: both shell scripts contain zero CRLF bytes.
- Local `diff --check`: passed.
- VPS syntax checks:
  - `/bin/sh -n scripts/pg_backup.sh`
  - `/bin/sh -n scripts/pg_restore_drill.sh`
- VPS backup:
  - `PG_BACKUP_OK /home/deploy/nexus-osint/backups/postgres/nexusosint-20260511T033857Z.sql.gz`
  - Backup file exists with mode `0600`, size `2.7K`.
- VPS restore drill:
  - Restored `backups/postgres/nexusosint-20260511T033857Z.sql.gz`.
  - `searches_count = 19`.
  - `PG_RESTORE_DRILL_OK backups/postgres/nexusosint-20260511T033857Z.sql.gz`.
- Bloat baseline:
  - `alembic_version`: live `1`, dead `0`.
  - `quota_log`: live `0`, dead `0`.
  - `rate_limits`: live `0`, dead `0`.
  - `searches`: live `19`, dead `0`.
  - `token_blacklist`: live `0`, dead `0`.
- Public health:
  - `https://nexusosint.uk/health` returned `status=healthy`, `rss_mb=78.0`,
    `agents_paused=false`, Redis reachable, and Postgres DB object present.

## Requirement Status

- DBM-47: deferred. Needs `pg_stat_statements` review after one week of real
  production traffic; earliest honest review date is 2026-05-17.
- DBM-48: deferred. Per-table autovacuum tuning for `searches` needs churn
  evidence from the same observation window.
- DBM-49: complete. Bloat baseline captured from `pg_stat_user_tables`.
- DBM-50: complete. `pg_dump` cron at 03:00 with 7-day retention is active.
- DBM-51: complete. Restore drill passed on the generated production backup.
- DBM-52: complete. Runtime `requirements.txt` already has no `aiosqlite`.
- DBM-53: complete. `CLAUDE.md` now reflects Postgres/asyncpg runtime rules and
  marks SQLite queue guidance obsolete.

## Deviations from Plan

- The local `scripts/pg_backup.sh` file was corrupted with NUL bytes before this
  run. It was restored and hardened rather than patched incrementally.
- Direct `root@87.99.153.11` SSH did not authenticate (`Permission denied (publickey)`).
  Deployment used the configured `hetzner` alias, which logs in as `deploy` and
  owns `/home/deploy/nexus-osint`.
- Local Docker was not running and local `bash.exe` points to WSL with no distro,
  so shell validation ran on the VPS with `/bin/sh -n`.

## Remaining Risks

- DBM-47/48 remain intentionally open until the one-week production observation
  window has real traffic evidence.
- Remote git state was not reconciled in this phase; only the required scripts
  and cron were updated on the VPS.

## Self-Check

PASSED

Backup automation, restore drill, runtime dependency cleanup verification, and
Postgres architecture docs are done. DBM-47/48 are documented as time-gated
deferrals, not completed work.
