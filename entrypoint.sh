#!/bin/sh
set -e
# Fix data dir ownership at runtime (volume mounts may reset it)
chown -R 1000:0 /app/data 2>/dev/null || true
chmod -R 770 /app/data 2>/dev/null || true
# Drop to appuser and exec uvicorn — equivalent to gosu, no extra package needed
exec python3 -c "
import os, sys
os.setgid(0)
os.setuid(1000)
os.execv('/usr/local/bin/uvicorn', [
    'uvicorn', 'api.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--proxy-headers'
])
"
