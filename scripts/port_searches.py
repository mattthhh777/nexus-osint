"""Port historical searches from SQLite to Postgres.

Idempotent by design: truncate Postgres `searches`, copy rows in batches, then
assert source/destination row-count parity.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
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


def convert_row(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        parse_ts(row["ts"]),
        row["username"],
        row["ip"],
        row["query"],
        row["query_type"],
        row["mode"],
        parse_modules(row["modules_run"]),
        int(row["breach_count"] or 0),
        int(row["stealer_count"] or 0),
        int(row["social_count"] or 0),
        row["elapsed_s"],
        bool(row["success"]) if row["success"] is not None else True,
        parse_payload(row["payload"] if "payload" in row.keys() else None),
    )


def iter_sqlite_batches(sqlite_path: Path, batch_size: int) -> Iterable[list[tuple[Any, ...]]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM searches ORDER BY ts, id")
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


async def port_searches(sqlite_path: Path, database_url: str, batch_size: int = BATCH_SIZE) -> int:
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
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    count = asyncio.run(port_searches(args.sqlite, args.database_url, args.batch_size))
    print(f"PORT_SEARCHES_OK rows={count}")


if __name__ == "__main__":
    main()
