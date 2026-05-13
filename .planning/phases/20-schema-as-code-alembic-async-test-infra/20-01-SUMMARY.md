# Plan 20-01 Summary - Postgres Schema and Test Infra

**Completed:** 2026-05-10
**Phase:** 20-schema-as-code-alembic-async-test-infra
**Plan:** 01

## Result

Phase 20 schema-as-code and test infrastructure are complete. The greenfield Postgres baseline now lives in Alembic using SQLAlchemy Core `MetaData`/`Table` definitions, with an ephemeral Postgres 16 test service on port `5433`.

## Changed

- Added async Alembic runtime config:
  - `alembic.ini`
  - `migrations/env.py`
  - `migrations/script.py.mako`
- Added baseline migration:
  - `migrations/versions/0001_postgres_baseline.py`
- Added ephemeral test Postgres:
  - `docker-compose.test.yml`
- Updated test fixture strategy:
  - `tests/conftest.py`
- Aligned dependency target:
  - `requirements.txt` now pins `asyncpg==0.31.0`.

## Schema Guarantees

- `pgcrypto` enabled before tables.
- All table primary keys use UUID defaults via `gen_random_uuid()`.
- Timestamps use `TIMESTAMPTZ`.
- Booleans use `BOOLEAN`.
- Variable payloads use `JSONB`.
- `searches.modules_run` uses `TEXT[]`.
- `searches.payload` has a GIN index.
- Status/count constraints use CHECK constraints, not ENUM.
- No foreign keys exist in current schema, so DBM-17 is satisfied by absence; no missing FK indexes.

## Verification

- `rg -n "TIMESTAMP[^T]|CREATE TYPE| ENUM|from __future__ import annotations" migrations tests\conftest.py` -> no matches.
- `python -m compileall migrations tests\conftest.py` -> passed.
- `docker compose -f docker-compose.test.yml config --quiet` -> passed.
- `docker compose -f docker-compose.test.yml up -d test-postgres` -> passed.
- `alembic upgrade head` -> passed against live test Postgres.
- `pytest tests/test_db.py tests/test_db_stream.py -q` -> 10 passed.
- `pytest tests/test_port_searches.py -q` -> 3 passed.

## Notes

- `tests/conftest.py` runs Alembic upgrade via `asyncio.to_thread()` because Alembic's async env uses `asyncio.run()`; calling it directly inside an async pytest fixture would fail under a running event loop.
- Avoided a duplicate `token_blacklist.jti` index because `UNIQUE (jti)` already creates one.
- Current worktree already contains Phase 22-style `api/db.py` asyncpg driver code from prior work. Phase 20 did not modify that boundary drift.
