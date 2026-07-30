#!/usr/bin/env bash
set -euo pipefail

umask 077

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:=5432}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSFILE:?PGPASSFILE is required}"
: "${HERMES_BACKUP_DIR:?HERMES_BACKUP_DIR is required}"

test -r "$PGPASSFILE"
install -d -m 0700 "$HERMES_BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final="$HERMES_BACKUP_DIR/hermes-control-plane-$timestamp.dump"
temporary="$final.partial"
manifest="$final.sha256"

trap 'rm -f "$temporary"' EXIT

pg_dump \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$PGUSER" \
  --dbname="$PGDATABASE" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="$temporary"

pg_restore --list "$temporary" >/dev/null
chmod 0600 "$temporary"
mv "$temporary" "$final"
sha256sum "$final" >"$manifest"
chmod 0600 "$manifest"
trap - EXIT

printf 'backup=%s\nmanifest=%s\n' "$final" "$manifest"
