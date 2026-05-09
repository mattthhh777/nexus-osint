# Phase 25 Context - Post-Migration Hardening

## Boundary

Harden backups and observability immediately. One-week query tuning remains time-bound and can only be completed after real traffic.

## Locked Decisions

- Enable backup automation with 7-day retention.
- Run restore drill.
- Remove SQLite runtime dependency after production cutover is healthy.
- Document the now-current Postgres architecture.
- Do not add speculative indexes before traffic evidence.

