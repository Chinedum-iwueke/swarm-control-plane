#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 0 || { echo 'Run with sudo bash.' >&2; exit 1; }
test "$#" -eq 1 || { echo "usage: $0 <exact-control-plane-commit>" >&2; exit 1; }
commit="$1"
case "$commit" in *[!0-9a-f]*|'') echo 'Commit must be hexadecimal.' >&2; exit 1 ;; esac
test "${#commit}" -eq 40 || { echo 'Commit must be a full Git commit.' >&2; exit 1; }

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo=/home/omenka/Projects/swarm-control-plane
for file in \
  "$repo/worker/.venv/bin/python" \
  "$repo/worker/scripts/ri017_external_acquisition.py" \
  "$repo/backend/app/surveillance/approved_sources_v1.json" \
  "$repo/backend/app/surveillance/approved_external_sources_v1.json"; do
  test -f "$file" || { echo "Required RI-017 dependency missing: $file" >&2; exit 1; }
done
test "$(git -C "$repo" rev-parse HEAD)" = "$commit" || {
  echo 'Production checkout does not match the pinned source commit.' >&2
  exit 1
}
source /etc/invariance-swarm/pilot-operator.env
test -n "${SWARM_API_URL:-}" -a -n "${SWARM_ORCHESTRATOR_TOKEN:-}" || {
  echo 'Pilot operator API URL and token are required.' >&2
  exit 1
}

install -d -o root -g root -m 0700 /var/lib/invariance-swarm/ri017
printf '%s\n' "$SWARM_API_URL" | install -o root -g root -m 0600 \
  /dev/stdin /etc/invariance-swarm/ri017-api-url
printf '%s\n' "$SWARM_ORCHESTRATOR_TOKEN" | install -o root -g root -m 0600 \
  /dev/stdin /etc/invariance-swarm/ri017-orchestrator.token
install -o root -g root -m 0644 \
  "$source_dir/invariance-swarm-ri017-external-acquisition.service" \
  "$source_dir/invariance-swarm-ri017-external-acquisition.timer" \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now invariance-swarm-ri017-external-acquisition.timer
systemctl start invariance-swarm-ri017-external-acquisition.service
echo 'RI-017 governed external acquisition installed and started.'

