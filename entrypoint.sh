#!/bin/sh
set -e

if [ -n "${DATABASE_URL:-}" ]; then
    LOCK_ID=8765432100
    TIMEOUT_S=30
    START=$(date +%s)
    while true; do
        GOT=$(psql "$DATABASE_URL" -tAc "SELECT pg_try_advisory_lock($LOCK_ID)")
        [ "$GOT" = "t" ] && break
        [ $(($(date +%s) - START)) -ge $TIMEOUT_S ] && { echo "alembic lock timeout after ${TIMEOUT_S}s — another container may be wedged"; exit 1; }
        sleep 1
    done
    alembic upgrade head
    RC=$?
    psql "$DATABASE_URL" -tAc "SELECT pg_advisory_unlock($LOCK_ID)" >/dev/null
    exit $RC
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
