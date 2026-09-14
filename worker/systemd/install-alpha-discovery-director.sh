#!/usr/bin/env bash
set -euo pipefail

((EUID == 0)) || { printf 'Run this installer as root.\n' >&2; exit 1; }
root=/srv/invariance/swarm/repositories/swarm-control-plane
runtime=/srv/invariance/swarm/control-plane-runtime
unit=invariance-swarm-alpha-discovery-director.service
test -f "$runtime/compose.yaml"
test -f "$root/worker/systemd/$unit"
test -S /var/run/docker.sock
(
  cd "$runtime"
  docker compose run --rm --no-deps api \
    python -c 'from app.services.alpha_discovery import reconcile_all'
) || { printf 'Deployed API image lacks ALPHA-004.\n' >&2; exit 1; }
install -o root -g root -m 0644 "$root/worker/systemd/$unit" "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload
systemctl enable --now "$unit"
printf 'ALPHA-004 discovery director installed and started.\n'
