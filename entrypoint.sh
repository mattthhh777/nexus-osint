#!/bin/sh
set -e

if [ -n "${DATABASE_URL:-}" ]; then
    python3 - <<'PY'
import asyncio
import os
import subprocess
import sys
import time

import asyncpg

LOCK_ID = 8765432100
TIMEOUT_S = 30


async def main() -> int:
    db_url = os.environ["DATABASE_URL"]
    lock_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(lock_url, command_timeout=30)
    locked = False
    try:
        deadline = time.monotonic() + TIMEOUT_S
        while True:
            locked = bool(await conn.fetchval("SELECT pg_try_advisory_lock($1)", LOCK_ID))
            if locked:
                break
            if time.monotonic() >= deadline:
                print(
                    f"alembic lock timeout after {TIMEOUT_S}s - another container may be wedged",
                    file=sys.stderr,
                )
                return 1
            await asyncio.sleep(1)

        return subprocess.run(["alembic", "upgrade", "head"], check=False).returncode
    finally:
        if locked:
            try:
                await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_ID)
            except asyncpg.PostgresError as exc:
                print(f"alembic advisory unlock failed: {type(exc).__name__}", file=sys.stderr)
        await conn.close()


sys.exit(asyncio.run(main()))
PY
fi

# Fix data dir ownership at runtime (volume mounts may reset it).
chown -R 1000:0 /app/data 2>/dev/null || true
chmod -R 770 /app/data 2>/dev/null || true

# Drop to appuser and exec uvicorn. HOME must not point at /root after setuid.
exec python3 -c "
import os, sys
os.environ['HOME'] = '/tmp'
os.setgid(0)
os.setuid(1000)
os.execv('/usr/local/bin/uvicorn', [
    'uvicorn', 'api.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--workers', '1',
    '--timeout-graceful-shutdown', '30',
    '--proxy-headers',
    '--forwarded-allow-ips=172.16.0.0/12'
])
"
