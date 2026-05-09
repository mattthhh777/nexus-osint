"""Stress asyncpg pool behavior without consuming external OSINT APIs."""
from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime, timezone

import asyncpg


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


async def worker(pool: asyncpg.Pool, worker_id: int, iterations: int) -> None:
    for i in range(iterations):
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO rate_limits (key, ts) VALUES ($1, $2)",
                    (f"stress:{worker_id}:{i}", time.time()),
                )
                await conn.fetchval("SELECT COUNT(*) FROM rate_limits WHERE key LIKE 'stress:%'")


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


async def run(database_url: str, concurrency: int, iterations: int) -> dict[str, int | float]:
    pool = await asyncpg.create_pool(
        dsn=_asyncpg_url(database_url),
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    started = time.perf_counter()
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM rate_limits WHERE key LIKE 'stress:%'")

        await asyncio.gather(
            *(worker(pool, worker_id, iterations) for worker_id in range(concurrency))
        )

        async with pool.acquire() as conn:
            row_count = await conn.fetchval(
                "SELECT COUNT(*) FROM rate_limits WHERE key LIKE 'stress:%'"
            )

        idle_tx = await idle_in_transaction_count(pool)
        elapsed = round(time.perf_counter() - started, 3)
        expected = concurrency * iterations
        if row_count != expected:
            raise RuntimeError(f"lost rows: expected={expected} actual={row_count}")
        if idle_tx != 0:
            raise RuntimeError(f"idle transactions leaked: {idle_tx}")
        return {
            "rows": int(row_count),
            "idle_in_transaction": idle_tx,
            "elapsed_s": elapsed,
            "pool_idle_size": pool.get_idle_size(),
        }
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=25)
    args = parser.parse_args()

    result = asyncio.run(run(args.database_url, args.concurrency, args.iterations))
    print(
        "STRESS_POSTGRES_OK "
        f"rows={result['rows']} "
        f"idle_in_transaction={result['idle_in_transaction']} "
        f"pool_idle_size={result['pool_idle_size']} "
        f"elapsed_s={result['elapsed_s']}"
    )


if __name__ == "__main__":
    main()
