---
phase: 23-concurrency-memory-stress-test
status: passed
verified: 2026-05-10
requirements: [DBM-32, DBM-33, DBM-34, DBM-35, DBM-36, DBM-37]
---

# Phase 23 Verification

## Goal

Verify the Postgres runtime architecture under burst concurrency before the
irreversible cutover phase.

## Result

Passed. The stress gate produced no OOM, no idle-in-transaction leak, no lost
counter updates, and `/health` DB pool idle recovery returned to baseline.

## Must-Haves

| Requirement | Status | Evidence |
|---|---|---|
| DBM-32 | PASS | 10 concurrent workers x 25 iterations x 3 cycles plus cancellation bursts completed. |
| DBM-33 | PASS | Script and direct SQL both reported `idle in transaction = 0`. |
| DBM-34 | PASS | Postgres observed at `36.8MiB / 768MiB`. |
| DBM-35 | PASS | Nexus observed at `75.54MiB / 2.441GiB`. |
| DBM-36 | PASS | `/health` DB idle size recovered from `2` to `2`; post-stress `db.idle_size=2`. |
| DBM-37 | PASS | Stress row count matched atomic counter (`rows=762 counter=762` app-container gate). |

## Automated Checks

- `python -m compileall scripts\stress_postgres_pool.py` -> passed.
- Test Postgres stress -> passed.
- App-container stress through internal `DATABASE_URL` and `/health` -> passed.
- Host stress with `--require-docker-stats` -> passed.
- Direct `pg_stat_activity` check after stress -> `0`.

## Notes

- First app-container stress attempt exposed a script accounting bug: cancellation
  can occur after DB commit and before local append. The script now treats full
  bursts as the minimum expected rows and uses committed row count vs atomic
  counter for exact lost-update detection.
- The script creates and drops `nexus_phase23_stress_counters`; it leaves no
  persistent schema artifact after a normal run.

## Human Verification

None required for Phase 23. Phase 24 remains a maintenance-window operation.
