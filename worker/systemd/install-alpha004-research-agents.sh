#!/usr/bin/env bash
set -euo pipefail

((EUID == 0)) || { printf 'Installer must run as root.\n' >&2; exit 1; }
root=/home/omenka/Projects/swarm-control-plane/worker
for profile in intelligence researcher; do
  environment="/etc/invariance-swarm/alpha004-${profile}.env"
  test -f "$environment"
  test "$(stat -c '%U:%G:%a' "$environment")" = root:root:600
done
test -x "$root/.venv/bin/invariance-swarm-worker"
test -x /usr/bin/codex
install -d -o omenka -g omenka -m 0700 /home/omenka/Projects/swarm-agent-workspaces
for unit in \
  invariance-swarm-alpha004-intelligence.service \
  invariance-swarm-alpha004-researcher.service; do
  systemd-analyze verify "$root/systemd/$unit"
  install -o root -g root -m 0644 "$root/systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now \
  invariance-swarm-alpha004-intelligence.service \
  invariance-swarm-alpha004-researcher.service
printf 'ALPHA-004 supervised research agents installed and started.\n'
