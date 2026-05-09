# Phase 24 Context - Production Cutover

## Boundary

Execute the maintenance window: backup SQLite, run migrations, port `searches`, set `DATABASE_URL`, rebuild/restart Nexus, smoke test, then leave SQLite read-only on disk.

## Locked Decisions

- Cutover is irreversible without rollback.
- Pre-flight artifacts are mandatory.
- Read-only mode blocks writes during the window.
- No improvisation: use scripts and captured evidence.

