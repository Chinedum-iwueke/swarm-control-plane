#!/usr/bin/env bash
set -euo pipefail

runtime=/srv/invariance/swarm/control-plane-runtime
backup_directory="$runtime/backups"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_file="$backup_directory/swarm_control_${timestamp}.dump"

test -d "$backup_directory"
test "$(stat -c %G "$backup_directory")" = invariance-swarm-backup-readers

cd "$runtime"
umask 0027
docker compose exec -T postgres \
  pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --username=swarm_app \
  --dbname=swarm_control \
  > "$backup_file"
chmod 0640 "$backup_file"

test "$(stat -c %G "$backup_file")" = invariance-swarm-backup-readers
docker compose exec -T postgres pg_restore --list \
  < "$backup_file" \
  > /dev/null

printf 'Created and verified backup: %s\n' "$backup_file"
