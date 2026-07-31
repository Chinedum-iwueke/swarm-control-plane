#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this installer as root.\n' >&2
  exit 1
fi

repo=/srv/invariance/swarm/repositories/swarm-control-plane
unit=invariance-swarm-mission-supervisor.service
environment=/etc/invariance-swarm/mission-supervisor.env

test -x "$repo/worker/.venv/bin/invariance-swarm-mission-supervisor"
test -f "$environment"
test "$(stat -c '%U:%G' "$environment")" = root:root
mode="$(stat -c '%a' "$environment")"
if ((8#${mode} & 8#077)); then
  printf 'Supervisor environment has unsafe permissions.\n' >&2
  exit 1
fi
install -o root -g root -m 0644 "$repo/worker/systemd/$unit" "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload
printf 'Installed %s without enabling or starting it.\n' "$unit"
