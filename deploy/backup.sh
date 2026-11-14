#!/bin/bash
# Nightly logical backup. Install on the VM, not inside the database container.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${BACKUP_DIR:-/var/backups/rooftop}"
mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f "$ROOT/docker-compose.yml" exec -T db \
  pg_dump -U rooftop --clean --if-exists rooftop | gzip > "$DEST/rooftop-$STAMP.sql.gz"
docker compose -f "$ROOT/docker-compose.yml" exec -T db \
  pg_dump -U rooftop --clean --if-exists mlflow | gzip > "$DEST/mlflow-$STAMP.sql.gz"
find "$DEST" -name '*.sql.gz' -mtime +14 -delete
echo "Wrote $DEST/rooftop-$STAMP.sql.gz and mlflow-$STAMP.sql.gz"
