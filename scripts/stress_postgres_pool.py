"""Stress asyncpg pool behavior without consuming external OSINT APIs."""

import argparse
import asyncio
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import asyncpg


STRESS_KEY = "phase23"
STRESS_TABLE = "nexus_phase23_stress_counters"


class StressFailure(RuntimeError):
    """Phase 23 stress gate failed."""


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


def _parse_memory_bytes(raw: str) -> int:
    match = re.match(r"^\s*([0-9.]+)\s*([KMGT]?i?B)\s*$", raw)
    if match is None:
        raise ValueError(f"cannot parse Docker memory value: {raw!r}")
    value = float(match.group(1))
    unit = match.group(2)
    factors = {
        "B": 1,
        "kB": 1_000,
        "KiB": 1024,
        "MB": 1_000_000,
        "MiB": 1024**2,
        "GB": 1_000_000_000,
        "GiB": 1024**3,
    }
    return int(value * factors[unit])


def _docker_stats(container: str) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", container],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return None
    mem_usage = str(payload.get("MemUsage", "")).split("/")[0].strip()
    try:
        payload["MemUsageBytes"] = _parse_memory_bytes(mem_usage)
    except ValueError:
        payload["MemUsageBytes"] = None
    return payload


def _health_snapshot(url: str, timeout: float = 5.0) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            raw = response.read(1_000_000)
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


async def _ensure_stress_table(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {STRESS_TABLE} (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await conn.execute("DELETE FROM rate_limits WHERE key LIKE 'stress:%'")
            await conn.execute(f"DELETE FROM {STRESS_TABLE} WHERE key = $1", STRESS_KEY)
            await conn.execute(
                f"INSERT INTO {STRESS_TABLE} (key, value) VALUES ($1, 0)",
                STRESS_KEY,
            )


async def _cleanup_stress_data(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM rate_limits WHERE key LIKE 'stress:%'")
            await conn.execute(f"DROP TABLE IF EXISTS {STRESS_TABLE}")


async def worker(
    pool: asyncpg.Pool,
    cycle: int,
    worker_id: int,
    iterations: int,
    completed: list[str],
) -> None:
    for i in range(iterations):
        key = f"stress:{cycle}:{worker_id}:{i}"
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO rate_limits (key, ts) VALUES ($1, $2)",
                    key,
                    time.time(),
                )
                await conn.execute(
                    f"UPDATE {STRESS_TABLE} SET value = value + 1 WHERE key = $1",
                    STRESS_KEY,
                )
                await conn.fetchval("SELECT COUNT(*) FROM rate_limits WHERE key LIKE 'stress:%'")
        completed.append(key)


async def cancellable_worker(
    pool: asyncpg.Pool,
    cycle: int,
    worker_id: int,
    iterations: int,
    completed: list[str],
) -> None:
    try:
        await worker(pool, cycle, worker_id, iterations, completed)
    except asyncio.CancelledError:
        raise


async def idle_in_transaction_count(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND state = 'idle in transaction'
            """
        )
    return int(value or 0)


async def _counter_value(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            f"SELECT value FROM {STRESS_TABLE} WHERE key = $1",
            STRESS_KEY,
        )
    return int(value or 0)


async def _rate_limit_rows(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT COUNT(*) FROM rate_limits WHERE key LIKE 'stress:%'"
        )
    return int(value or 0)


async def _run_full_burst(
    pool: asyncpg.Pool,
    cycle: int,
    concurrency: int,
    iterations: int,
) -> int:
    completed: list[str] = []
    await asyncio.gather(
        *(worker(pool, cycle, worker_id, iterations, completed) for worker_id in range(concurrency))
    )
    return len(completed)


async def _run_cancel_burst(
    pool: asyncpg.Pool,
    cycle: int,
    concurrency: int,
    iterations: int,
    cancel_after_s: float,
) -> int:
    completed: list[str] = []
    tasks = [
        asyncio.create_task(cancellable_worker(pool, cycle, worker_id, iterations, completed))
        for worker_id in range(concurrency)
    ]
    await asyncio.sleep(cancel_after_s)
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    unexpected = [
        result for result in results
        if not isinstance(result, asyncio.CancelledError) and result is not None
    ]
    if unexpected:
        first = unexpected[0]
        if isinstance(first, asyncpg.PostgresError):
            raise StressFailure(f"cancel burst database error: {type(first).__name__}") from first
        if isinstance(first, OSError):
            raise StressFailure(f"cancel burst OS error: {type(first).__name__}") from first
        raise StressFailure(f"cancel burst unexpected result: {type(first).__name__}")
    return len(completed)


async def run(
    database_url: str,
    concurrency: int,
    iterations: int,
    cycles: int,
    cancel_after_s: float,
) -> dict[str, int | float]:
    pool = await asyncpg.create_pool(
        dsn=_asyncpg_url(database_url),
        min_size=2,
        max_size=10,
        command_timeout=30,
        server_settings={"idle_in_transaction_session_timeout": "60s"},
    )
    started = time.perf_counter()
    expected_min_rows = 0
    try:
        await _ensure_stress_table(pool)

        for cycle in range(cycles):
            expected_min_rows += await _run_full_burst(pool, cycle, concurrency, iterations)
            await _run_cancel_burst(
                pool,
                cycle,
                concurrency,
                iterations,
                cancel_after_s,
            )
            idle_tx = await idle_in_transaction_count(pool)
            if idle_tx != 0:
                raise StressFailure(f"idle transactions leaked after cycle {cycle}: {idle_tx}")

        row_count = await _rate_limit_rows(pool)
        counter_value = await _counter_value(pool)

        idle_tx = await idle_in_transaction_count(pool)
        elapsed = round(time.perf_counter() - started, 3)
        if row_count < expected_min_rows:
            raise StressFailure(f"lost rows: expected_at_least={expected_min_rows} actual={row_count}")
        if counter_value != row_count:
            raise StressFailure(
                f"lost counter updates: expected={row_count} actual={counter_value}"
            )
        if idle_tx != 0:
            raise StressFailure(f"idle transactions leaked: {idle_tx}")
        return {
            "rows": int(row_count),
            "counter": int(counter_value),
            "idle_in_transaction": idle_tx,
            "elapsed_s": elapsed,
            "pool_size": pool.get_size(),
            "pool_idle_size": pool.get_idle_size(),
        }
    finally:
        await _cleanup_stress_data(pool)
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL"),
    )
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--cancel-after-s", type=float, default=0.02)
    parser.add_argument("--health-url", default=os.getenv("NEXUS_HEALTH_URL"))
    parser.add_argument("--postgres-container", default="nexus-postgres")
    parser.add_argument("--nexus-container", default="nexus-osint")
    parser.add_argument("--postgres-memory-limit-mb", type=int, default=768)
    parser.add_argument("--nexus-memory-limit-mb", type=int, default=2500)
    parser.add_argument("--require-docker-stats", action="store_true")
    parser.add_argument("--require-health", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    before_health = _health_snapshot(args.health_url) if args.health_url else None
    before_postgres_stats = _docker_stats(args.postgres_container)
    before_nexus_stats = _docker_stats(args.nexus_container)

    result = asyncio.run(
        run(
            args.database_url,
            args.concurrency,
            args.iterations,
            args.cycles,
            args.cancel_after_s,
        )
    )

    after_health = _health_snapshot(args.health_url) if args.health_url else None
    after_postgres_stats = _docker_stats(args.postgres_container)
    after_nexus_stats = _docker_stats(args.nexus_container)

    if args.require_health and after_health is None:
        raise SystemExit("health snapshot required but unavailable")

    if args.require_docker_stats and (after_postgres_stats is None or after_nexus_stats is None):
        raise SystemExit("Docker stats required but unavailable")

    postgres_bytes = (
        after_postgres_stats.get("MemUsageBytes")
        if after_postgres_stats is not None
        else None
    )
    nexus_bytes = (
        after_nexus_stats.get("MemUsageBytes")
        if after_nexus_stats is not None
        else None
    )
    if postgres_bytes is not None and postgres_bytes > args.postgres_memory_limit_mb * 1024 * 1024:
        raise SystemExit("postgres memory exceeded limit")
    if nexus_bytes is not None and nexus_bytes > args.nexus_memory_limit_mb * 1024 * 1024:
        raise SystemExit("nexus memory exceeded limit")

    before_idle = None
    after_idle = None
    if before_health is not None:
        before_idle = (before_health.get("db") or {}).get("idle_size")
    if after_health is not None:
        after_idle = (after_health.get("db") or {}).get("idle_size")

    print(
        "STRESS_POSTGRES_OK "
        f"rows={result['rows']} "
        f"counter={result['counter']} "
        f"idle_in_transaction={result['idle_in_transaction']} "
        f"pool_size={result['pool_size']} "
        f"pool_idle_size={result['pool_idle_size']} "
        f"elapsed_s={result['elapsed_s']} "
        f"health_idle_before={before_idle} "
        f"health_idle_after={after_idle} "
        f"postgres_mem_mb={round(postgres_bytes / 1024 / 1024, 1) if postgres_bytes is not None else 'unavailable'} "
        f"nexus_mem_mb={round(nexus_bytes / 1024 / 1024, 1) if nexus_bytes is not None else 'unavailable'}"
    )


if __name__ == "__main__":
    main()
