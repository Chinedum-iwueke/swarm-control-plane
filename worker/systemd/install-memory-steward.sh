#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

root=/home/omenka/Projects/swarm-control-plane/worker
unit=invariance-swarm-research-memory-steward.service
test -x "$root/.venv/bin/invariance-swarm-worker"
test -f /etc/invariance-swarm/vm1-memory-steward.env
test -d /home/omenka/Projects/bulletproof_bt
test -d /home/omenka/Projects/swarm-agent-workspaces
install -o root -g root -m 0644 "$root/systemd/$unit" "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload
echo "Installed $unit without enabling or starting it."
