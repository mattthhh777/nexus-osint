#!/bin/sh
set -eu

BACKUP_DIR="${PG_BACKUP_DIR:-/home/deploy/nexus-osint/backups/postgres}"
RETENTION_DAYS="${PG_BACKUP_RETENTION_DAYS:-7}"
CONTAINER="${POSTGRES_CONTAINER:-nexus-postgres}"
DB="${POSTGRES_DB:-nexusosint}"
USER="${POSTGRES_USER:-nexus}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/nexusosint-$stamp.sql.gz"

docker exec "$CONTAINER" pg_dump -U "$USER" "$DB" | gzip -9 > "$target"
chmod 600 "$target"

find "$BACKUP_DIR" -type f -name 'nexusosint-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
echo "PG_BACKUP_OK $target"
