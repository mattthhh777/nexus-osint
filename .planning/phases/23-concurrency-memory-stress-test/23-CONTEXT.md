# Phase 23 Context - Stress Gate

## Boundary

Run a production-like Postgres pool stress gate before cutover. Avoid external OSINT API consumption by testing DB and health behavior locally and on VPS.

## Locked Decisions

- Verify pool recovery and zero idle transactions.
- Verify Postgres and Nexus memory budgets.
- Verify concurrent writes do not lose counters/rows.
- Red gate blocks Phase 24.

