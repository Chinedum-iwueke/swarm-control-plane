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
test -f /etc/invariance-swarm/codex-worker/auth.json
runtime=/var/lib/invariance-swarm/codex-discovery-runtime
test ! -L "$runtime"
install -d -o omenka -g omenka -m 0700 "$runtime"
test ! -L "$runtime/auth.json"
if [[ ! -e "$runtime/auth.json" ]]; then
  install -o root -g root -m 0600 /dev/null "$runtime/auth.json"
fi
install -o root -g root -m 0600 "$root/systemd/codex-discovery-runtime.env" \
  /etc/invariance-swarm/codex-discovery-runtime.env
install -d -o omenka -g omenka -m 0700 /home/omenka/Projects/swarm-agent-workspaces
for unit in \
  invariance-swarm-alpha004-intelligence.service \
  invariance-swarm-alpha004-researcher.service; do
  systemd-analyze verify "$root/systemd/$unit"
  install -o root -g root -m 0644 "$root/systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable \
  invariance-swarm-alpha004-intelligence.service \
  invariance-swarm-alpha004-researcher.service
systemctl restart \
  invariance-swarm-alpha004-intelligence.service \
  invariance-swarm-alpha004-researcher.service
printf 'ALPHA-004 supervised research agents installed and started.\n'
