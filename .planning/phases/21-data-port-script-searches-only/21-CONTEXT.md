# Phase 21 Context - Data Port Script

## Boundary

Port only historical `searches` rows from SQLite to Postgres. Do not migrate users, Redis cache, sessions, or rate limiter history beyond schema requirements.

## Locked Decisions

- Script is idempotent: truncate `searches`, then load and assert parity.
- Use `asyncpg.copy_records_to_table`.
- Batch size is 1000.
- Convert SQLite ISO text timestamps to timezone-aware datetimes.
- Convert comma-separated `modules_run` to `TEXT[]`.
- Convert integer `success` to boolean.
- Legacy missing payload becomes `{}`.

