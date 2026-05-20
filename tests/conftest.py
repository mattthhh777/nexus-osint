"""Pytest fixtures for the Postgres-backed database layer."""

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config

from api.db import DatabaseManager


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://nexus:nexus@localhost:5433/nexusosint_test",
    )
    return url


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


@pytest_asyncio.fixture
async def tmp_db(test_database_url: str) -> DatabaseManager:
    try:
        conn = await asyncpg.connect(_asyncpg_url(test_database_url), timeout=2)
    except (TimeoutError, asyncio.TimeoutError, OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Postgres test database unavailable: {type(exc).__name__}")
    else:
        await conn.close()

    cfg = Config(str(Path("alembic.ini")))
    cfg.set_main_option("sqlalchemy.url", test_database_url)
    await asyncio.to_thread(command.upgrade, cfg, "head")

    manager = DatabaseManager(database_url=test_database_url, min_size=1, max_size=4)
    await manager.startup()
    try:
        for table in (
            "search_events",
            "search_jobs",
            "searches",
            "token_blacklist",
            "rate_limits",
            "quota_log",
        ):
            await manager.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        yield manager
    finally:
        await manager.shutdown()
