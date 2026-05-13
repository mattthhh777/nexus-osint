#!/bin/sh
set -eu

BACKUP_DIR="${PG_BACKUP_DIR:-/home/deploy/nexus-osint/backups/postgres}"
RETENTION_DAYS="${PG_BACKUP_RETENTION_DAYS:-7}"
CONTAINER="${POSTGRES_CONTAINER:-nexus-postgres}"
DB="${POSTGRES_DB:-nexusosint}"
USER="${POSTGRES_USER:-nexus}"
LOCK_DIR="${PG_BACKUP_LOCK_DIR:-/tmp/nexus-pg-backup.lock}"

case "$RETENTION_DAYS" in
  ''|*[!0-9]*)
    echo "PG_BACKUP_ERROR invalid PG_BACKUP_RETENTION_DAYS: $RETENTION_DAYS" >&2
    exit 2
    ;;
esac

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "PG_BACKUP_SKIPPED another backup is already running" >&2
  exit 0
fi

tmp_sql=""
tmp_gz=""
cleanup() {
  [ -n "$tmp_sql" ] && [ -f "$tmp_sql" ] && rm -f "$tmp_sql"
  [ -n "$tmp_gz" ] && [ -f "$tmp_gz" ] && rm -f "$tmp_gz"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/nexusosint-$stamp.sql.gz"
tmp_sql="$(mktemp "$BACKUP_DIR/.nexusosint-$stamp.XXXXXX.sql")"
tmp_gz="$(mktemp "$BACKUP_DIR/.nexusosint-$stamp.XXXXXX.sql.gz")"

docker exec "$CONTAINER" pg_dump \
  -U "$USER" \
  -d "$DB" \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  > "$tmp_sql"

gzip -9 -c "$tmp_sql" > "$tmp_gz"
gzip -t "$tmp_gz"
chmod 600 "$tmp_gz"
mv "$tmp_gz" "$target"
tmp_gz=""

find "$BACKUP_DIR" -type f -name 'nexusosint-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete

echo "PG_BACKUP_OK $target"
