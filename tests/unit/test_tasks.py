import asyncio
import logging

import pytest

from api import tasks
from api.db import DatabaseError


class DummyDb:
    def __init__(self) -> None:
        self.blacklist_calls = 0

    async def execute_nowait(self, sql, params=()) -> None:
        self.blacklist_calls += 1


def two_step_sleep():
    calls = {"count": 0}

    async def sleep(_interval):
        calls["count"] += 1
        if calls["count"] > 1:
            raise asyncio.CancelledError

    return sleep


@pytest.mark.asyncio
async def test_job_cleanup_loop_calls_purge_expired(monkeypatch) -> None:
    db = DummyDb()
    purged = []

    async def fake_purge_expired(*, db):
        purged.append(db)
        return 2

    monkeypatch.setattr(tasks.asyncio, "sleep", two_step_sleep())
    monkeypatch.setattr(tasks.job_store, "purge_expired", fake_purge_expired)

    with pytest.raises(asyncio.CancelledError):
        await tasks.job_cleanup_loop(db, interval=3600)

    assert purged == [db]


@pytest.mark.asyncio
async def test_job_cleanup_loop_retries_after_database_error(monkeypatch, caplog) -> None:
    db = DummyDb()
    purged = []

    async def fake_purge_expired(*, db):
        purged.append(db)
        raise DatabaseError("temporary failure")

    monkeypatch.setattr(tasks.asyncio, "sleep", two_step_sleep())
    monkeypatch.setattr(tasks.job_store, "purge_expired", fake_purge_expired)

    caplog.set_level(logging.WARNING, logger="nexusosint.tasks")
    with pytest.raises(asyncio.CancelledError):
        await tasks.job_cleanup_loop(db, interval=3600)

    assert purged == [db]
    assert "job_cleanup_loop: DB error - will retry next cycle" in caplog.text


@pytest.mark.asyncio
async def test_blacklist_purge_loop_triggers_job_cleanup_without_startup_edit(monkeypatch) -> None:
    db = DummyDb()
    purged = []

    async def fake_purge_expired(*, db):
        purged.append(db)
        return 1

    monkeypatch.setattr(tasks.asyncio, "sleep", two_step_sleep())
    monkeypatch.setattr(tasks.job_store, "purge_expired", fake_purge_expired)

    with pytest.raises(asyncio.CancelledError):
        await tasks.blacklist_purge_loop(db, interval=60, job_cleanup_interval=0)

    assert db.blacklist_calls == 1
    assert purged == [db]
