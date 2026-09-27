#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 0 || { echo "Run with sudo bash." >&2; exit 1; }
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /etc/invariance-swarm/pilot-operator.env
test -n "${SWARM_ORCHESTRATOR_TOKEN:-}"
install -d -o root -g root -m 0755 /etc/invariance-swarm
printf '%s\n' "$SWARM_ORCHESTRATOR_TOKEN" | install -o root -g root -m 0600 /dev/stdin /etc/invariance-swarm/orchestrator.token
install -o root -g root -m 0644 \
  "$source_dir/invariance-swarm-codex-auth-watcher.service" \
  /etc/systemd/system/invariance-swarm-codex-auth-watcher.service
systemctl daemon-reload
systemctl enable --now invariance-swarm-codex-auth-watcher.service
systemctl is-active --quiet invariance-swarm-codex-auth-watcher.service
echo "Codex authentication watcher installed and active."
