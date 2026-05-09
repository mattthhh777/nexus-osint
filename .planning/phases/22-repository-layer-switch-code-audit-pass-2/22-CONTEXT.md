# Phase 22 Context - Repository Layer Switch

## Boundary

Replace the runtime DB driver behind the Phase 17 abstraction with asyncpg. Application SQL call sites must use Postgres-compatible SQL. This phase does not execute production cutover; it makes the image cutover-ready.

## Locked Decisions

- Use `asyncpg.Pool` with `min_size=2`, `max_size=10`, `command_timeout=30`.
- Delete SQLite write queue architecture.
- Use `$N` placeholders at call sites.
- Use `ON CONFLICT DO NOTHING/UPDATE` instead of SQLite conflict syntax.
- Health exposes pool idle size.
- `execute_nowait` remains in the interface but becomes an awaited direct execute; callers already await it.

