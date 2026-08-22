#!/usr/bin/env bash
set -euo pipefail

backup_directory=/srv/invariance/swarm/control-plane-runtime/backups
failure="$backup_directory/latest-failure.json"
temporary="$failure.partial"

record_failure() {
  rc=$?
  printf '{"failed_at":"%s","return_code":%d}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" > "$temporary"
  chmod 0640 "$temporary"
  mv -f "$temporary" "$failure"
  exit "$rc"
}
trap record_failure ERR

umask 0027
/opt/invariance-swarm-worker/bin/invariance-swarm-control-plane-backup create
rm -f "$failure" "$temporary"
