#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this installer as root.\n' >&2
  exit 1
fi

start=false
enable=false
for argument in "$@"; do
  case "$argument" in
    --start) start=true ;;
    --enable) enable=true ;;
    *)
      printf 'Unknown argument: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done

repo=/srv/invariance/swarm/repositories/swarm-control-plane
worker="$repo/worker"
unit=invariance-swarm-deployment-architect.service
environment=/etc/invariance-swarm/vm2-deployment-architect.env

test -x "$worker/.venv/bin/invariance-swarm-infrastructure-worker"
test -f "$environment"
test "$(stat -c '%U:%G' "$environment")" = root:root
mode="$(stat -c '%a' "$environment")"
if ((8#${mode} & 8#077)); then
  printf 'Deployment architect environment has unsafe permissions.\n' >&2
  exit 1
fi
getent group invariance-swarm-infrastructure >/dev/null
id swarm-infrastructure >/dev/null 2>&1

install -d \
  -o swarm-infrastructure \
  -g invariance-swarm-infrastructure \
  -m 0700 \
  /srv/invariance/swarm/agent-workspaces/deployment-architect
install -o root -g root -m 0644 \
  "$worker/systemd/$unit" \
  "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload

if $enable; then
  systemctl enable "$unit"
fi
if $start; then
  systemctl start "$unit"
fi
printf 'Deployment architect installed. enable=%s start=%s\n' "$enable" "$start"
