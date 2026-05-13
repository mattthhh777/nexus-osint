---
phase: 25-post-migration-tuning-backup-hardening
status: gaps_found
verified: 2026-05-11
requirements-verified: [DBM-49, DBM-50, DBM-51, DBM-52, DBM-53]
requirements-pending: [DBM-47, DBM-48]
source:
  - .planning/phases/25-post-migration-tuning-backup-hardening/25-01-SUMMARY.md
---

# Phase 25 Verification

## Verdict

Gaps found, but they are time-gated rather than implementation misses. Phase 25
backup hardening is complete; Postgres tuning requirements DBM-47 and DBM-48
must wait until at least 2026-05-17 because the production Postgres cutover
completed on 2026-05-10.

## Verified

- DBM-49: `pg_stat_user_tables` bloat baseline captured.
  - `searches`: `n_live_tup=19`, `n_dead_tup=0`.
  - Other app tables also show `n_dead_tup=0`.
- DBM-50: VPS crontab contains the 03:00 `scripts/pg_backup.sh` entry with
  `PG_BACKUP_DIR=/home/deploy/nexus-osint/backups/postgres`.
- DBM-51: Restore drill passed on
  `backups/postgres/nexusosint-20260511T033857Z.sql.gz`; restored
  `searches_count=19`.
- DBM-52: `requirements.txt` contains no `aiosqlite`.
- DBM-53: `CLAUDE.md` now documents PostgreSQL/asyncpg runtime rules and marks
  SQLite queue guidance obsolete.

## Automated Checks

- `python -m pytest tests/test_port_searches.py tests/test_db.py -q --tb=short`
  -> `5 passed, 7 skipped`.
- `diff --check` -> passed.
- VPS `/bin/sh -n` for both backup scripts -> passed.
- Public `https://nexusosint.uk/health` -> `status=healthy`, Redis reachable,
  Postgres DB object present, `agents_paused=false`.

## Gaps

- DBM-47: Pending. Review `pg_stat_statements` after one week production
  traffic; add partial indexes only for confirmed hot paths.
- DBM-48: Pending. Apply `searches` autovacuum tuning only if churn evidence
  justifies it after the same observation window.

## Next Action

On or after 2026-05-17, run the Postgres observation review and close DBM-47/48
with measured evidence. Do not add speculative indexes or autovacuum overrides
before that review.
