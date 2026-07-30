#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this uninstaller as root.\n' >&2
  exit 1
fi

stop=false
disable=false
for argument in "$@"; do
  case "$argument" in
    --stop) stop=true ;;
    --disable) disable=true ;;
    *)
      printf 'Unknown argument: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done

if $stop; then
  systemctl stop invariance-swarm-infrastructure-worker.service || true
  systemctl stop invariance-swarm-infrastructure-broker.service || true
fi
if $disable; then
  systemctl disable invariance-swarm-infrastructure-worker.service || true
  systemctl disable invariance-swarm-infrastructure-broker.service || true
fi

unlink /etc/systemd/system/invariance-swarm-infrastructure-worker.service \
  2>/dev/null || true
unlink /etc/systemd/system/invariance-swarm-infrastructure-broker.service \
  2>/dev/null || true
systemctl daemon-reload
printf 'Infrastructure units removed. Credentials and evidence were preserved.\n'
