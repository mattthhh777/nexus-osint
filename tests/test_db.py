"""
tests/test_db.py — Unit tests for api/db.py DatabaseManager.

Test coverage:
  1. WAL mode is active after startup
  2. Schema: all 4 tables exist after startup
  3. Write serialization: 50 concurrent writes complete without lock errors
  4. Read-during-write: reads return immediately while writes are queued
  5. Startup/shutdown lifecycle: data persists across manager instances
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from api.db import DatabaseManager


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _table_exists(db: DatabaseManager, table: str) -> bool:
    row = await db.read_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return row is not None


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wal_mode(tmp_db: DatabaseManager) -> None:
    """PRAGMA journal_mode must return 'wal' after startup."""
    row = await tmp_db.read_one("PRAGMA journal_mode")
    assert row is not None, "PRAGMA journal_mode returned None"
    # aiosqlite.Row keyed by column name — SQLite returns the pragma value
    # in the first (and only) column, key varies by driver version
    value = list(row.values())[0]
    assert value == "wal", f"Expected WAL mode, got {value!r}"


@pytest.mark.asyncio
async def test_schema_tables_exist(tmp_db: DatabaseManager) -> None:
    """All 4 tables must exist after startup."""
    for table in ("searches", "token_blacklist", "rate_limits", "quota_log"):
        exists = await _table_exists(tmp_db, table)
        assert exists, f"Table '{table}' was not created by startup()"


@pytest.mark.asyncio
async def test_write_serialization(tmp_db: DatabaseManager) -> None:
    """50 concurrent writes must all succeed with zero lock errors."""
    insert_sql = "INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES (?,?,?,?)"

    # Fire 50 concurrent write_await calls — each waits for confirmation
    tasks = [
        tmp_db.write_await(insert_sql, (f"2026-01-01T00:00:{i:02d}Z", i, 100 - i, 100))
        for i in range(50)
    ]
    # If any write fails, this will raise an exception
    await asyncio.gather(*tasks)

    rows = await tmp_db.read_all("SELECT COUNT(*) as cnt FROM quota_log")
    assert rows[0]["cnt"] == 50, f"Expected 50 rows, found {rows[0]['cnt']}"


@pytest.mark.asyncio
async def test_read_during_write(tmp_db: DatabaseManager) -> None:
    """
    Reads must not block while the write queue has pending items.
    We queue 10 writes, then immediately issue a read — the read should
    return promptly because WAL allows concurrent readers.
    """
    insert_sql = "INSERT INTO rate_limits (key, ts) VALUES (?,?)"

    # Queue 10 writes (fire-and-forget — they go on the queue but are not awaited yet)
    for i in range(10):
        await tmp_db.write(insert_sql, (f"test_key_{i}", float(i)))

    # Read immediately while writes may still be processing
    row = await tmp_db.read_one("SELECT COUNT(*) as cnt FROM searches")
    assert row is not None
    assert isinstance(row["cnt"], int)


@pytest.mark.asyncio
async def test_startup_shutdown_persists(tmp_path: Path) -> None:
    """Data written before shutdown must be readable after a new startup."""
    db_path = tmp_path / "persist_test.db"

    # First manager: write data, then shut down
    mgr1 = DatabaseManager(db_path=db_path)
    await mgr1.startup()
    await mgr1.write_await(
        "INSERT INTO searches "
        "(ts, username, ip, query, query_type, mode, modules_run, elapsed_s, success) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("2026-01-01T00:00:00Z", "testuser", "127.0.0.1", "test_query",
         "username", "automated", "breach", 1.5, 1),
    )
    await mgr1.shutdown()

    # Second manager: open same file, verify the row is there
    mgr2 = DatabaseManager(db_path=db_path)
    await mgr2.startup()
    row = await mgr2.read_one(
        "SELECT username FROM searches WHERE query = ?", ("test_query",)
    )
    await mgr2.shutdown()

    assert row is not None, "Row written before shutdown was not found after restart"
    assert row["username"] == "testuser"
