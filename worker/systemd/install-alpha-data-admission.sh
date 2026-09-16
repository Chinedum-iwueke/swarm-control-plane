#!/usr/bin/env bash
set -euo pipefail

((EUID == 0)) || { printf 'Run this installer as root.\n' >&2; exit 1; }

root=/home/omenka/Projects/swarm-control-plane
native=/home/omenka/Projects/bulletproof_bt
environment=/etc/invariance-swarm/alpha-data-admission.env
state=/etc/invariance-swarm/alpha-data-admission-state.json
unit=invariance-swarm-alpha-data-admission.service

for file in \
  "$root/worker/.venv/bin/invariance-swarm-worker" \
  "$root/worker/systemd/$unit" \
  "$native/.venv/bin/python" \
  "$native/scripts/build_alpha_data_admission_batch.py" \
  "$environment" \
  "$state"; do
  test -f "$file" || { printf 'Required admission runtime file is missing: %s\n' "$file" >&2; exit 1; }
done

for file in "$environment" "$state"; do
  test "$(stat -c '%u:%a' "$file")" = '0:600' || {
    printf 'Require root-owned mode 600: %s\n' "$file" >&2
    exit 1
  }
done

test "$(sed -n 's/^SWARM_AGENT_SLUG=//p' "$environment")" = vm1-alpha-data-admission
grep -Fq '"slug": "vm1-alpha-data-admission"' "$state"

install -d -o omenka -g omenka -m 0700 \
  /home/omenka/.local/share/invariance-swarm/alpha-data-backups
install -o root -g root -m 0644 \
  "$root/worker/systemd/$unit" "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload
systemctl enable --now "$unit"
printf 'ALPHA-008 selected-panel data admission worker installed and started.\n'
