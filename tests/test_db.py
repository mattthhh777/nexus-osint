"""Tests for the asyncpg-backed DatabaseManager."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from api.db import DatabaseManager


async def _table_exists(db: DatabaseManager, table: str) -> bool:
    row = await db.fetch_one(
        "SELECT 1 AS found FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1",
        (table,),
    )
    return row is not None


@pytest.mark.asyncio
async def test_schema_tables_exist(tmp_db: DatabaseManager) -> None:
    for table in ("searches", "token_blacklist", "rate_limits", "quota_log"):
        assert await _table_exists(tmp_db, table)


@pytest.mark.asyncio
async def test_pool_stats_expose_idle_size(tmp_db: DatabaseManager) -> None:
    stats = tmp_db.pool_stats()
    assert stats["started"] is True
    assert stats["max_size"] == 4
    assert isinstance(stats["idle_size"], int)


@pytest.mark.asyncio
async def test_concurrent_writes_complete_without_lost_rows(tmp_db: DatabaseManager) -> None:
    insert_sql = (
        "INSERT INTO quota_log (ts, used_today, left_today, daily_limit) "
        "VALUES ($1, $2, $3, $4)"
    )

    tasks = [
        tmp_db.execute(
            insert_sql,
            (datetime.now(timezone.utc), i, 100 - i, 100),
        )
        for i in range(50)
    ]
    await asyncio.gather(*tasks)

    row = await tmp_db.fetch_one("SELECT COUNT(*) AS cnt FROM quota_log")
    assert row == {"cnt": 50}


@pytest.mark.asyncio
async def test_quota_log_retention_keeps_100_newest_by_ts(tmp_db: DatabaseManager) -> None:
    for i in range(200):
        await tmp_db.execute(
            "INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES ($1, $2, $3, $4)",
            (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), i, 200 - i, 200),
        )

    await tmp_db.execute(
        "DELETE FROM quota_log WHERE id NOT IN "
        "(SELECT id FROM quota_log ORDER BY ts DESC LIMIT 100)"
    )

    row = await tmp_db.fetch_one("SELECT COUNT(*) AS cnt FROM quota_log")
    assert row == {"cnt": 100}


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
