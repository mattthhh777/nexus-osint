#!/bin/sh
set -e

if [ -n "${DATABASE_URL:-}" ]; then
    alembic upgrade head
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
