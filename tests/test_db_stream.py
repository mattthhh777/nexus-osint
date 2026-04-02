"""
tests/test_db_stream.py — Tests for DatabaseManager.read_stream() async generator.

Coverage:
  1. read_stream() yields all rows from a 100-row table
  2. read_stream(batch_size=10) yields rows in batches without loading all into memory
  3. read_stream() on an empty table yields nothing (no error)
  4. read_all() still returns a full list (backward compat)
  5. read_one() still returns a single dict or None (backward compat)
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from pathlib import Path

from api.db import DatabaseManager


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def stream_db(tmp_path: Path) -> DatabaseManager:
    """DatabaseManager with a small test table pre-populated with 100 rows."""
    db_path = tmp_path / "stream_test.db"
    manager = DatabaseManager(db_path=db_path)
    await manager.startup()

    # Create a dedicated test table (separate from production schema)
    assert manager._conn is not None
    await manager._conn.execute(
        "CREATE TABLE IF NOT EXISTS test_items (id INTEGER PRIMARY KEY, value TEXT)"
    )
    await manager._conn.commit()

    # Insert 100 rows via write_await so they are confirmed before tests run
    for i in range(100):
        await manager.write_await(
            "INSERT INTO test_items (id, value) VALUES (?, ?)",
            (i + 1, f"item_{i + 1}"),
        )

    yield manager
    await manager.shutdown()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_stream_yields_all_rows(stream_db: DatabaseManager) -> None:
    """read_stream() must yield all 100 rows from the table."""
    rows = []
    async for row in stream_db.read_stream("SELECT * FROM test_items ORDER BY id"):
        rows.append(row)
    assert len(rows) == 100, f"Expected 100 rows, got {len(rows)}"
    assert rows[0]["id"] == 1
    assert rows[99]["id"] == 100


@pytest.mark.asyncio
async def test_read_stream_batch_size(stream_db: DatabaseManager) -> None:
    """read_stream(batch_size=10) must yield all 100 rows with no row skipped or duplicated."""
    rows = []
    async for row in stream_db.read_stream(
        "SELECT * FROM test_items ORDER BY id", batch_size=10
    ):
        rows.append(row)
    assert len(rows) == 100, f"Expected 100 rows, got {len(rows)}"
    # Verify unique ids — no duplicates, no gaps
    ids = [r["id"] for r in rows]
    assert ids == list(range(1, 101)), "Row ids are not sequential 1..100"


@pytest.mark.asyncio
async def test_read_stream_empty_table(stream_db: DatabaseManager) -> None:
    """read_stream() on an empty table must yield nothing without raising."""
    # Create an empty table
    assert stream_db._conn is not None
    await stream_db._conn.execute(
        "CREATE TABLE IF NOT EXISTS empty_table (id INTEGER PRIMARY KEY)"
    )
    await stream_db._conn.commit()

    rows = []
    async for row in stream_db.read_stream("SELECT * FROM empty_table"):
        rows.append(row)
    assert rows == [], f"Expected no rows from empty table, got {rows}"


@pytest.mark.asyncio
async def test_read_all_backward_compat(stream_db: DatabaseManager) -> None:
    """read_all() must still return a full list of dicts (backward compat)."""
    rows = await stream_db.read_all("SELECT * FROM test_items ORDER BY id")
    assert isinstance(rows, list), f"read_all() should return list, got {type(rows)}"
    assert len(rows) == 100
    assert rows[0]["id"] == 1


@pytest.mark.asyncio
async def test_read_one_backward_compat(stream_db: DatabaseManager) -> None:
    """read_one() must still return a single dict or None (backward compat)."""
    row = await stream_db.read_one(
        "SELECT * FROM test_items WHERE id = ?", (42,)
    )
    assert row is not None, "read_one() returned None for existing row"
    assert row["id"] == 42
    assert row["value"] == "item_42"

    missing = await stream_db.read_one(
        "SELECT * FROM test_items WHERE id = ?", (9999,)
    )
    assert missing is None, "read_one() should return None for non-existent row"
