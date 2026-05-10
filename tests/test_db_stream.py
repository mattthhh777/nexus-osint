"""Tests for DatabaseManager stream helpers on Postgres."""

import pytest
import pytest_asyncio

from api.db import DatabaseManager


@pytest_asyncio.fixture
async def stream_db(tmp_db: DatabaseManager) -> DatabaseManager:
    await tmp_db.execute("DROP TABLE IF EXISTS test_items")
    await tmp_db.execute("DROP TABLE IF EXISTS empty_table")
    await tmp_db.execute("CREATE TABLE test_items (id integer PRIMARY KEY, value text)")
    for i in range(100):
        await tmp_db.execute(
            "INSERT INTO test_items (id, value) VALUES ($1, $2)",
            (i + 1, f"item_{i + 1}"),
        )
    return tmp_db


@pytest.mark.asyncio
async def test_read_stream_yields_all_rows(stream_db: DatabaseManager) -> None:
    rows = [row async for row in stream_db.read_stream("SELECT * FROM test_items ORDER BY id")]
    assert len(rows) == 100
    assert rows[0]["id"] == 1
    assert rows[99]["id"] == 100


@pytest.mark.asyncio
async def test_read_stream_batch_size(stream_db: DatabaseManager) -> None:
    rows = [
        row
        async for row in stream_db.read_stream(
            "SELECT * FROM test_items ORDER BY id", batch_size=10
        )
    ]
    assert [row["id"] for row in rows] == list(range(1, 101))


@pytest.mark.asyncio
async def test_read_stream_empty_table(stream_db: DatabaseManager) -> None:
    await stream_db.execute("CREATE TABLE empty_table (id integer PRIMARY KEY)")
    rows = [row async for row in stream_db.read_stream("SELECT * FROM empty_table")]
    assert rows == []


@pytest.mark.asyncio
async def test_read_all_backward_compat(stream_db: DatabaseManager) -> None:
    rows = await stream_db.read_all("SELECT * FROM test_items ORDER BY id")
    assert isinstance(rows, list)
    assert len(rows) == 100
    assert rows[0]["id"] == 1


@pytest.mark.asyncio
async def test_read_one_backward_compat(stream_db: DatabaseManager) -> None:
    row = await stream_db.read_one("SELECT * FROM test_items WHERE id = $1", (42,))
    assert row == {"id": 42, "value": "item_42"}

    missing = await stream_db.read_one("SELECT * FROM test_items WHERE id = $1", (9999,))
    assert missing is None
