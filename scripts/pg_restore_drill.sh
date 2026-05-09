#!/bin/sh
set -eu

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ]; then
  echo "usage: scripts/pg_restore_drill.sh /path/to/backup.sql.gz" >&2
  exit 2
fi

CONTAINER="${POSTGRES_CONTAINER:-nexus-postgres}"
USER="${POSTGRES_USER:-nexus}"
DRILL_DB="${PG_RESTORE_DRILL_DB:-nexusosint_restore_drill}"

docker exec "$CONTAINER" psql -U "$USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DRILL_DB"
docker exec "$CONTAINER" psql -U "$USER" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DRILL_DB"
gzip -dc "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$USER" -d "$DRILL_DB" -v ON_ERROR_STOP=1 >/dev/null
docker exec "$CONTAINER" psql -U "$USER" -d "$DRILL_DB" -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS searches_count FROM searches"
docker exec "$CONTAINER" psql -U "$USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE $DRILL_DB"
echo "PG_RESTORE_DRILL_OK $BACKUP_FILE"
