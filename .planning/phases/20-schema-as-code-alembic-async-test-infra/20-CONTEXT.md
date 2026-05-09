# Phase 20 Context - Schema-as-Code + Alembic Async + Test Infra

## Boundary

Create the Postgres schema and test infrastructure before application cutover. No production data migration and no app driver switch in this phase.

## Locked Decisions

- Use Alembic async migrations.
- Baseline schema is greenfield Postgres, not a SQLite clone.
- Primary keys use UUID defaults via `gen_random_uuid()` where a primary key exists.
- Timestamps use `TIMESTAMPTZ`.
- Booleans use `BOOLEAN`.
- Variable payloads use `JSONB`.
- Status-like fields use `CHECK`, not ENUM.
- `searches.payload` gets a GIN index.
- Every FK must have explicit indexes; current schema has no FK relationships.
- Test Postgres runs as an ephemeral Compose service on host port `5433`.

## Canonical References

- `.planning/REQUIREMENTS.md` - DBM-11 through DBM-19.
- `.planning/ROADMAP.md` - Phase 20 deliverable and verification.
- `api/db.py` - current schema source of truth before migration.
- `.planning/phases/17-v4-2-pre-migration-audit-db-abstraction-layer/SQL_INVENTORY.md` - SQL inventory.

