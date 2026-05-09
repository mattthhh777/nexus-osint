"""Tests for the Phase 17 database abstraction contract."""
from __future__ import annotations

import asyncio

import pytest

from api.db import DatabaseError, DatabaseManager


@pytest.mark.asyncio
async def test_fetch_one_returns_dict_or_none(tmp_db: DatabaseManager) -> None:
    await tmp_db.execute(
        "INSERT INTO rate_limits (key, ts) VALUES ($1, $2)",
        ("fetch_one", 1.0),
    )

    row = await tmp_db.fetch_one(
        "SELECT key, ts FROM rate_limits WHERE key = $1",
        ("fetch_one",),
    )
    missing = await tmp_db.fetch_one(
        "SELECT key, ts FROM rate_limits WHERE key = $1",
        ("missing",),
    )

    assert row == {"key": "fetch_one", "ts": 1.0}
    assert missing is None


@pytest.mark.asyncio
async def test_fetch_all_returns_list_of_dicts(tmp_db: DatabaseManager) -> None:
    await tmp_db.execute("INSERT INTO rate_limits (key, ts) VALUES ($1, $2)", ("a", 1.0))
    await tmp_db.execute("INSERT INTO rate_limits (key, ts) VALUES ($1, $2)", ("b", 2.0))

    rows = await tmp_db.fetch_all("SELECT key FROM rate_limits ORDER BY key")

    assert rows == [{"key": "a"}, {"key": "b"}]


@pytest.mark.asyncio
async def test_failed_execute_raises_database_error(tmp_db: DatabaseManager) -> None:
    with pytest.raises(DatabaseError):
        await tmp_db.execute("INSERT INTO missing_table (value) VALUES ($1)", ("x",))


@pytest.mark.asyncio
async def test_transaction_commits_on_success(tmp_db: DatabaseManager) -> None:
    async with tmp_db.transaction() as tx:
        await tx.execute("INSERT INTO rate_limits (key, ts) VALUES ($1, $2)", ("tx_commit", 1.0))

    row = await tmp_db.fetch_one(
        "SELECT key FROM rate_limits WHERE key = $1",
        ("tx_commit",),
    )
    assert row == {"key": "tx_commit"}


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_exception(tmp_db: DatabaseManager) -> None:
    with pytest.raises(ValueError):
        async with tmp_db.transaction() as tx:
            await tx.execute(
                "INSERT INTO rate_limits (key, ts) VALUES ($1, $2)",
                ("tx_rollback", 1.0),
            )
            raise ValueError("force rollback")

    row = await tmp_db.fetch_one(
        "SELECT key FROM rate_limits WHERE key = $1",
        ("tx_rollback",),
    )
    assert row is None


@pytest.mark.asyncio
async def test_parallel_write_can_commit_while_transaction_is_open(tmp_db: DatabaseManager) -> None:
    async with tmp_db.transaction() as tx:
        await tx.execute("INSERT INTO rate_limits (key, ts) VALUES ($1, $2)", ("inside", 1.0))
        outside = asyncio.create_task(
            tmp_db.execute("INSERT INTO rate_limits (key, ts) VALUES ($1, $2)", ("outside", 2.0))
        )

        await outside

    rows = await tmp_db.fetch_all("SELECT key FROM rate_limits ORDER BY ts")
    assert rows == [{"key": "inside"}, {"key": "outside"}]
