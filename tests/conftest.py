"""
tests/conftest.py — pytest fixtures for NexusOSINT test suite.

Provides a DatabaseManager instance backed by a temporary on-disk SQLite file
so tests exercise the real WAL mode and write-queue behavior without touching
production data.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from api.db import DatabaseManager


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default asyncio event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture
async def tmp_db(tmp_path: Path) -> DatabaseManager:
    """
    Yield a fully started DatabaseManager backed by a temp file.
    Shutdown is called automatically after each test.
    """
    db_path = tmp_path / "test_audit.db"
    manager = DatabaseManager(db_path=db_path)
    await manager.startup()
    yield manager
    await manager.shutdown()
