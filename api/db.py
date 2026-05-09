"""
NexusOSINT database manager.

Postgres runtime:
  - asyncpg.Pool owned by the FastAPI lifespan
  - SQL uses native $1/$2 placeholders
  - Alembic owns schema creation
  - No background write queue; Postgres handles concurrent writes
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator, Optional

import asyncpg

from api.config import DATABASE_URL

logger = logging.getLogger("nexusosint.db")


class DatabaseError(Exception):
    """Database operation failed inside the current driver implementation."""


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


def _row_dict(row: asyncpg.Record | None) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


class Transaction:
    """Transaction facade for code that needs multiple DB operations atomically."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        try:
            return _row_dict(await self._conn.fetchrow(sql, *params))
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database transaction fetch_one failed") from exc

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        try:
            return [dict(row) for row in await self._conn.fetch(sql, *params)]
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database transaction fetch_all failed") from exc

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        try:
            await self._conn.execute(sql, *params)
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database transaction execute failed") from exc


class DatabaseManager:
    """Small asyncpg pool wrapper matching the Phase 17 DB abstraction contract."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        min_size: int = 2,
        max_size: int = 10,
        command_timeout: float = 30.0,
    ) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None
        self._min_size = min_size
        self._max_size = max_size
        self._command_timeout = command_timeout
        self._started = False

    async def startup(self, database_url: str | None = None, **_: Any) -> None:
        if self._started:
            logger.warning("DatabaseManager.startup() called more than once - ignoring")
            return

        url = database_url or self._database_url or DATABASE_URL
        if not url:
            raise RuntimeError("DATABASE_URL is required for Postgres runtime")

        try:
            self._pool = await asyncpg.create_pool(
                dsn=_asyncpg_url(url),
                min_size=self._min_size,
                max_size=self._max_size,
                command_timeout=self._command_timeout,
                server_settings={"idle_in_transaction_session_timeout": "60s"},
            )
        except (asyncpg.PostgresError, OSError) as exc:
            raise DatabaseError("database startup failed") from exc

        self._started = True
        logger.info(
            "DatabaseManager started - asyncpg pool min=%d max=%d",
            self._min_size,
            self._max_size,
        )

    async def shutdown(self) -> None:
        if not self._started:
            return
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        self._started = False
        logger.info("DatabaseManager shutdown complete")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DatabaseManager not started - call startup() first")
        return self._pool

    def pool_stats(self) -> dict[str, int | bool]:
        if self._pool is None:
            return {
                "started": False,
                "min_size": self._min_size,
                "max_size": self._max_size,
                "size": 0,
                "idle_size": 0,
            }
        return {
            "started": self._started,
            "min_size": self._min_size,
            "max_size": self._max_size,
            "size": self._pool.get_size(),
            "idle_size": self._pool.get_idle_size(),
        }

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if not self._started:
            raise RuntimeError("DatabaseManager not started - call startup() first")
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(sql, *params)
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database execute failed") from exc

    async def execute_nowait(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        await self.execute(sql, params)

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        if not self._started:
            raise RuntimeError("DatabaseManager not started - call startup() first")
        try:
            async with self.pool.acquire() as conn:
                return _row_dict(await conn.fetchrow(sql, *params))
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database fetch_one failed") from exc

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        if not self._started:
            raise RuntimeError("DatabaseManager not started - call startup() first")
        try:
            async with self.pool.acquire() as conn:
                return [dict(row) for row in await conn.fetch(sql, *params)]
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database fetch_all failed") from exc

    async def fetch_stream(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        batch_size: int = 50,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not self._started:
            raise RuntimeError("DatabaseManager not started - call startup() first")
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    async for row in conn.cursor(sql, *params, prefetch=batch_size):
                        yield dict(row)
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database fetch_stream failed") from exc

    read_one = fetch_one
    read_all = fetch_all
    read = fetch_all
    read_stream = fetch_stream
    write_await = execute
    write = execute_nowait

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        if not self._started:
            raise RuntimeError("DatabaseManager not started - call startup() first")
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    yield Transaction(conn)
        except asyncpg.PostgresError as exc:
            raise DatabaseError("database transaction failed") from exc


db = DatabaseManager()
