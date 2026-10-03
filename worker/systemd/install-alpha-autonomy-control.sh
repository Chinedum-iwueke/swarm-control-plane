#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
install -o root -g root -m 0644 \
  "$root/worker/systemd/invariance-swarm-alpha-autonomy-control.service" \
  /etc/systemd/system/invariance-swarm-alpha-autonomy-control.service
install -d -o omenka -g omenka -m 0700 \
  /home/omenka/.local/state/invariance-swarm
systemctl daemon-reload
systemctl enable --now invariance-swarm-alpha-autonomy-control.service
echo "Audited autonomy drain-state synchronization installed and active."
