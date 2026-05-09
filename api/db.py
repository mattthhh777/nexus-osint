"""
NexusOSINT — Database Manager (api/db.py)
SQLite hardening: single persistent connection + WAL mode + write serialization via asyncio.Queue.

Design:
  - One aiosqlite connection for the entire process lifetime
  - WAL mode: concurrent reads never block writes (and vice versa)
  - asyncio.Queue: all writes are serialized through a background writer task
  - Reads go direct (WAL allows concurrent readers safely)
  - All DDL consolidated in startup() — no inline schema creation anywhere else

Usage:
    from api.db import db

    await db.startup()               # call once at app startup
    await db.execute_nowait(sql, params) # fire-and-forget write
    await db.execute(sql, params)        # write + wait for confirmation
    row  = await db.fetch_one(sql, params)
    rows = await db.fetch_all(sql, params)
    await db.shutdown()              # call at app shutdown
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Optional

import aiosqlite

logger = logging.getLogger("nexusosint.db")

# Sentinel object to signal the writer loop to exit
_STOP_SENTINEL = object()


class DatabaseError(Exception):
    """Database operation failed inside the current driver implementation."""


class Transaction:
    """Small transaction facade matching the future Postgres-facing DB contract."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        try:
            async with self._conn.execute(sql, params) as cur:
                row = await cur.fetchone()
                return dict(row) if row is not None else None
        except aiosqlite.Error as exc:
            raise DatabaseError("database transaction fetch_one failed") from exc

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        try:
            async with self._conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
                return [dict(row) for row in rows]
        except aiosqlite.Error as exc:
            raise DatabaseError("database transaction fetch_all failed") from exc

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        try:
            await self._conn.execute(sql, params)
        except aiosqlite.Error as exc:
            raise DatabaseError("database transaction execute failed") from exc


class DatabaseManager:
    """
    Manages a single persistent SQLite connection with WAL mode and
    serialized writes via asyncio.Queue.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path: Optional[Path] = db_path  # set at startup if not provided
        self._conn: Optional[aiosqlite.Connection] = None
        self._write_queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=1000)
        self._writer_task: Optional[asyncio.Task[None]] = None
        self._tx_lock: asyncio.Lock = asyncio.Lock()
        self._started: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def startup(self, db_path: Optional[Path] = None) -> None:
        """
        Open the database connection, configure PRAGMAs, create all tables,
        and start the background writer task.

        Must be called exactly once before any read/write operations.
        """
        if self._started:
            logger.warning("DatabaseManager.startup() called more than once — ignoring")
            return

        if db_path is not None:
            self._db_path = db_path

        if self._db_path is None:
            raise RuntimeError("DatabaseManager requires a db_path before startup()")

        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = await aiosqlite.connect(str(self._db_path))
            self._conn.row_factory = aiosqlite.Row
        except aiosqlite.Error as exc:
            raise DatabaseError("database startup failed") from exc

        # ── PRAGMAs ───────────────────────────────────────────────────────────
        try:
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA synchronous=NORMAL")     # safe with WAL, 2x faster
            await self._conn.execute("PRAGMA busy_timeout=5000")       # wait 5s instead of failing
            await self._conn.execute("PRAGMA cache_size=-8000")        # 8MB cache
            await self._conn.execute("PRAGMA wal_autocheckpoint=100")  # checkpoint every 100 pages
            await self._conn.commit()
        except aiosqlite.Error as exc:
            raise DatabaseError("database pragma initialization failed") from exc

        # ── Schema: all DDL in one place ──────────────────────────────────────
        try:
            await self._create_schema()
        except aiosqlite.Error as exc:
            raise DatabaseError("database schema initialization failed") from exc

        # ── Start background writer ───────────────────────────────────────────
        self._writer_task = asyncio.create_task(
            self._writer_loop(), name="db-writer"
        )
        self._started = True
        logger.info("DatabaseManager started — WAL mode active, writer task running")

    async def shutdown(self) -> None:
        """
        Drain the write queue, stop the background writer, and close the connection.
        Safe to call even if startup() was never called.
        """
        if not self._started:
            return

        # Signal writer to stop after draining remaining queue entries
        await self._write_queue.put(_STOP_SENTINEL)

        if self._writer_task is not None:
            try:
                await asyncio.wait_for(self._writer_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("DB writer task did not stop in 10s — cancelling")
                self._writer_task.cancel()
                try:
                    await self._writer_task
                except asyncio.CancelledError:
                    pass

        if self._conn is not None:
            await self._conn.close()
            self._conn = None

        self._started = False
        logger.info("DatabaseManager shutdown complete")

    # ── Schema ────────────────────────────────────────────────────────────────

    async def _create_schema(self) -> None:
        """Create all tables. Called once during startup()."""
        assert self._conn is not None

        # searches — audit log for every query run
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            TEXT    NOT NULL,
                username      TEXT    NOT NULL,
                ip            TEXT,
                query         TEXT    NOT NULL,
                query_type    TEXT,
                mode          TEXT,
                modules_run   TEXT,
                breach_count  INTEGER DEFAULT 0,
                stealer_count INTEGER DEFAULT 0,
                social_count  INTEGER DEFAULT 0,
                elapsed_s     REAL,
                success       INTEGER DEFAULT 1
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ts ON searches(ts)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user ON searches(username)"
        )

        # token_blacklist — revoked JWT JTIs until expiry
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS token_blacklist (
                jti TEXT PRIMARY KEY,
                exp INTEGER NOT NULL
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bl_exp ON token_blacklist(exp)"
        )

        # rate_limits — persistent rate limiting that survives restarts
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                key  TEXT NOT NULL,
                ts   REAL NOT NULL
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_key ON rate_limits(key)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_key_ts ON rate_limits(key, ts)"
        )

        # quota_log — OathNet API quota tracking for admin dashboard
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS quota_log (
                id          INTEGER PRIMARY KEY,
                ts          TEXT    NOT NULL,
                used_today  INTEGER,
                left_today  INTEGER,
                daily_limit INTEGER
            )
        """)
        await self._ensure_quota_log_id_column()

        await self._conn.commit()
        logger.debug("Database schema verified/created")

    async def _ensure_quota_log_id_column(self) -> None:
        """Rebuild legacy quota_log tables that predate the explicit id PK."""
        assert self._conn is not None
        async with self._conn.execute("PRAGMA table_info(quota_log)") as cur:
            rows = await cur.fetchall()
        if any(row["name"] == "id" for row in rows):
            return

        logger.info("Migrating legacy quota_log table to explicit id primary key")
        await self._conn.execute("ALTER TABLE quota_log RENAME TO quota_log_legacy")
        await self._conn.execute("""
            CREATE TABLE quota_log (
                id          INTEGER PRIMARY KEY,
                ts          TEXT    NOT NULL,
                used_today  INTEGER,
                left_today  INTEGER,
                daily_limit INTEGER
            )
        """)
        await self._conn.execute("""
            INSERT INTO quota_log (ts, used_today, left_today, daily_limit)
            SELECT ts, used_today, left_today, daily_limit
            FROM quota_log_legacy
            ORDER BY ts
        """)
        await self._conn.execute("DROP TABLE quota_log_legacy")

    # ── Writer loop ───────────────────────────────────────────────────────────

    async def _writer_loop(self) -> None:
        """
        Background task: processes write operations from the queue serially.
        Each item in the queue is a tuple of (sql, params, future_or_none).
        When future is not None, it is resolved with the result so write_await() callers
        can wait for confirmation.
        """
        while True:
            item = await self._write_queue.get()

            if item is _STOP_SENTINEL:
                self._write_queue.task_done()
                break

            sql, params, fut = item
            try:
                assert self._conn is not None
                async with self._tx_lock:
                    await self._conn.execute(sql, params)
                    await self._conn.commit()
                if fut is not None and not fut.done():
                    fut.get_loop().call_soon_threadsafe(fut.set_result, None)
            except aiosqlite.Error as exc:
                db_exc = DatabaseError("database write failed")
                db_exc.__cause__ = exc
                logger.error("DB write error â€” sql=%r params=%r error=%s", sql, params, exc)
                if fut is not None and not fut.done():
                    try:
                        fut.get_loop().call_soon_threadsafe(fut.set_exception, db_exc)
                    except Exception:
                        pass
            except Exception as exc:
                logger.error("DB write error — sql=%r params=%r error=%s", sql, params, exc)
                if fut is not None and not fut.done():
                    try:
                        fut.get_loop().call_soon_threadsafe(fut.set_exception, exc)
                    except Exception:
                        pass
            finally:
                self._write_queue.task_done()

    # ── Write operations (via queue) ──────────────────────────────────────────

    async def write(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """
        Fire-and-forget write. Puts the operation on the queue and returns immediately.
        Errors are logged but not propagated to the caller.
        The queue serializes all writes — no lock contention.
        """
        if not self._started:
            logger.warning("DB write called before startup() — sql=%r", sql)
            return
        try:
            self._write_queue.put_nowait((sql, params, None))
            qsize = self._write_queue.qsize()
            if qsize > 800:  # >80% of maxsize=1000
                logger.warning("DB write queue at %d/1000 — approaching capacity", qsize)
        except asyncio.QueueFull:
            logger.error("DB write queue full (maxsize=1000) — dropping write: sql=%r", sql)

    async def write_await(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """
        Write via queue and wait for completion.
        Use when the caller needs confirmation that the write succeeded before proceeding.
        Raises the original exception if the write fails.
        """
        if not self._started:
            raise RuntimeError("DatabaseManager not started — call startup() first")

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()

        try:
            self._write_queue.put_nowait((sql, params, fut))
        except asyncio.QueueFull as exc:
            raise RuntimeError("DB write queue full — cannot write") from exc

        await fut

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Canonical blocking write alias for the driver abstraction layer."""
        await self.write_await(sql, params)

    async def execute_nowait(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Canonical fire-and-forget write alias for the driver abstraction layer."""
        await self.write(sql, params)

    # ── Read operations (direct, WAL allows concurrent reads) ─────────────────

    async def read(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """
        Execute a read query and return all rows as a list of dicts.
        Direct access — WAL mode allows concurrent reads without blocking writes.
        """
        if not self._started:
            raise RuntimeError("DatabaseManager not started — call startup() first")
        assert self._conn is not None
        try:
            async with self._conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
                return [dict(row) for row in rows]
        except aiosqlite.Error as exc:
            raise DatabaseError("database read failed") from exc

    async def read_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Alias for read() — returns all matching rows as a list of dicts."""
        return await self.read(sql, params)

    async def read_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        """
        Execute a read query and return the first row as a dict, or None if no rows.
        Direct access — WAL mode allows concurrent reads without blocking writes.
        """
        if not self._started:
            raise RuntimeError("DatabaseManager not started — call startup() first")
        assert self._conn is not None
        try:
            async with self._conn.execute(sql, params) as cur:
                row = await cur.fetchone()
                return dict(row) if row is not None else None
        except aiosqlite.Error as exc:
            raise DatabaseError("database read_one failed") from exc

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        """Canonical read-one alias for the driver abstraction layer."""
        return await self.read_one(sql, params)

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Canonical read-all alias for the driver abstraction layer."""
        return await self.read_all(sql, params)

    async def read_stream(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        batch_size: int = 50,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute a read query and yield rows one at a time as dicts.

        Uses fetchmany(batch_size) internally to balance memory vs round-trips.
        Preferred over read_all() for large result sets (> 100 rows) to avoid
        loading the full result into memory on the 1GB VPS.

        Direct access — WAL mode allows concurrent reads without blocking writes.
        """
        if not self._started:
            raise RuntimeError("DatabaseManager not started — call startup() first")
        assert self._conn is not None
        try:
            async with self._conn.execute(sql, params) as cur:
                while True:
                    rows = await cur.fetchmany(batch_size)
                    if not rows:
                        break
                    for row in rows:
                        yield dict(row)
        except aiosqlite.Error as exc:
            raise DatabaseError("database read_stream failed") from exc

    async def fetch_stream(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        batch_size: int = 50,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Canonical stream alias for the driver abstraction layer."""
        async for row in self.read_stream(sql, params, batch_size):
            yield row

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        """Run multiple statements atomically on the underlying connection."""
        if not self._started:
            raise RuntimeError("DatabaseManager not started â€” call startup() first")
        assert self._conn is not None

        async with self._tx_lock:
            try:
                await self._conn.execute("BEGIN IMMEDIATE")
                yield Transaction(self._conn)
                await self._conn.commit()
            except aiosqlite.Error as exc:
                await self._conn.rollback()
                raise DatabaseError("database transaction failed") from exc
            except Exception:
                await self._conn.rollback()
                raise


# ── Module-level singleton ────────────────────────────────────────────────────

db = DatabaseManager()
