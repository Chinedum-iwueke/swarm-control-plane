#!/usr/bin/env bash
set -euo pipefail

unit=invariance-swarm-alpha-research-executor-v2.service
old_unit=invariance-swarm-alpha-research-executor.service
root=/home/omenka/Projects/swarm-control-plane/worker
environment=/etc/invariance-swarm/alpha003-executor.env

((EUID == 0)) || { printf 'Installer must run as root.\n' >&2; exit 1; }
test -f "$root/systemd/$unit"
test -x "$root/.venv/bin/invariance-swarm-worker"
test -f "$environment"
test "$(stat -c '%U:%G:%a' "$environment")" = root:root:600
test -x /home/omenka/Projects/bulletproof_bt/.venv/bin/python

install -d -o omenka -g omenka -m 0700 /home/omenka/Projects/swarm-agent-workspaces
install -d -o omenka -g omenka -m 0700 /home/omenka/.local/state/invariance-swarm
install -d -o omenka -g omenka -m 0700 /home/omenka/.local/share/invariance-swarm/alpha002-bundles
systemd-analyze verify "$root/systemd/$unit"
install -o root -g root -m 0644 "$root/systemd/$unit" "/etc/systemd/system/$unit"
systemctl daemon-reload
systemctl disable --now "$old_unit" 2>/dev/null || true
systemctl enable --now "$unit"
printf 'ALPHA-003 governed scientific executor installed and v1 lease consumer retired.\n'
