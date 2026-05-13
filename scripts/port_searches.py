"""Port historical searches from SQLite to Postgres.

Idempotent by design: truncate Postgres `searches`, copy rows in batches, then
assert source/destination row-count parity.
"""

import argparse
import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

import asyncpg

BATCH_SIZE = 1000
SEARCH_COLUMNS = (
    "ts",
    "username",
    "ip",
    "query",
    "query_type",
    "mode",
    "modules_run",
    "breach_count",
    "stealer_count",
    "social_count",
    "elapsed_s",
    "success",
    "payload",
)
CONFIRM_TRUNCATE_VALUE = "truncate-and-port-searches"


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


def parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text) if text else datetime.now(timezone.utc)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def parse_modules(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_payload(value: Any) -> str:
    if value in (None, ""):
        return "{}"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    try:
        json.loads(str(value))
        return str(value)
    except json.JSONDecodeError:
        return "{}"


def _row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def convert_row(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        parse_ts(_row_value(row, "ts")),
        _row_value(row, "username", ""),
        _row_value(row, "ip"),
        _row_value(row, "query", ""),
        _row_value(row, "query_type"),
        _row_value(row, "mode"),
        parse_modules(_row_value(row, "modules_run")),
        int(_row_value(row, "breach_count", 0) or 0),
        int(_row_value(row, "stealer_count", 0) or 0),
        int(_row_value(row, "social_count", 0) or 0),
        _row_value(row, "elapsed_s"),
        bool(_row_value(row, "success")) if _row_value(row, "success") is not None else True,
        parse_payload(_row_value(row, "payload")),
    )


def _sqlite_order_clause(conn: sqlite3.Connection) -> str:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(searches)").fetchall()}
    if "id" in columns:
        return "ORDER BY ts, id"
    return "ORDER BY ts"


def iter_sqlite_batches(sqlite_path: Path, batch_size: int) -> Iterable[list[tuple[Any, ...]]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(f"SELECT * FROM searches {_sqlite_order_clause(conn)}")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield [convert_row(row) for row in rows]
    finally:
        conn.close()


def sqlite_count(sqlite_path: Path) -> int:
    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM searches").fetchone()
        return int(row[0])
    finally:
        conn.close()


async def port_searches(
    sqlite_path: Path,
    database_url: str,
    batch_size: int = BATCH_SIZE,
    *,
    confirm_truncate: bool = False,
) -> int:
    if not confirm_truncate:
        raise RuntimeError(
            "Refusing to truncate Postgres searches without explicit confirmation"
        )

    source_count = sqlite_count(sqlite_path)
    conn = await asyncpg.connect(_asyncpg_url(database_url))
    try:
        async with conn.transaction():
            await conn.execute("TRUNCATE TABLE searches")
            for batch in iter_sqlite_batches(sqlite_path, batch_size):
                await conn.copy_records_to_table(
                    "searches",
                    records=batch,
                    columns=SEARCH_COLUMNS,
                )

            dest_count = await conn.fetchval("SELECT COUNT(*) FROM searches")
            if dest_count != source_count:
                raise RuntimeError(
                    f"row-count parity failed: sqlite={source_count} postgres={dest_count}"
                )
    finally:
        await conn.close()
    return source_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument(
        "--confirm-truncate",
        choices=[CONFIRM_TRUNCATE_VALUE],
        help="Required confirmation. This truncates Postgres searches before loading.",
    )
    args = parser.parse_args()

    if args.confirm_truncate != CONFIRM_TRUNCATE_VALUE:
        parser.error(
            f"--confirm-truncate {CONFIRM_TRUNCATE_VALUE!r} is required; "
            "target Postgres searches will be truncated"
        )
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    started = perf_counter()
    count = asyncio.run(
        port_searches(
            args.sqlite,
            args.database_url,
            args.batch_size,
            confirm_truncate=True,
        )
    )
    elapsed_s = perf_counter() - started
    print(f"PORT_SEARCHES_OK rows={count} elapsed_s={elapsed_s:.3f}")


if __name__ == "__main__":
    main()
