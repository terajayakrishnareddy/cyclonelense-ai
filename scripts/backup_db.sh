#!/bin/sh
# Dump the PostgreSQL database from the running compose stack to a timestamped, compressed file.
#   ./scripts/backup_db.sh [output_dir]
set -e
out="${1:-backups}"; mkdir -p "$out"
f="$out/cyclonelens-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' | gzip > "$f"
echo "Wrote $f"
