#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

enable=false
start=false
for argument in "$@"; do
  case "$argument" in
    --enable) enable=true ;;
    --start) start=true ;;
    *) echo "Unknown option: $argument" >&2; exit 2 ;;
  esac
done
if [[ "$start" == true && "$enable" != true ]]; then
  echo "--start requires --enable." >&2
  exit 2
fi

root=/srv/invariance/swarm/repositories/swarm-control-plane
runtime=/srv/invariance/swarm/control-plane-runtime
unit=invariance-swarm-research-ingestion-recovery-steward.service
test -f "$runtime/compose.yaml"
test -f "$root/worker/systemd/$unit"
test -S /var/run/docker.sock
test -d /etc/invariance-swarm/codex-recovery
test "$(stat -c %u /etc/invariance-swarm/codex-recovery)" = 10001
test "$(stat -c %a /etc/invariance-swarm/codex-recovery)" = 700
install -o root -g root -m 0644 \
  "$root/worker/systemd/$unit" "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload
if [[ "$enable" == true ]]; then
  systemctl enable "$unit"
fi
if [[ "$start" == true ]]; then
  systemctl restart "$unit"
fi
echo "Recovery steward installed. enable=$enable start=$start"
