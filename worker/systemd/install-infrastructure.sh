#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this installer as root.\n' >&2
  exit 1
fi

start=false
enable=false
restart=false
for argument in "$@"; do
  case "$argument" in
    --start) start=true ;;
    --enable) enable=true ;;
    --restart) restart=true ;;
    *)
      printf 'Unknown argument: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done

repo=/srv/invariance/swarm/repositories/swarm-control-plane
worker="$repo/worker"
test -x "$worker/.venv/bin/invariance-swarm-infrastructure-worker"
test -x "$worker/.venv/bin/invariance-swarm-infrastructure-broker"
test -d /srv/invariance/swarm/control-plane-runtime
test -S /var/run/docker.sock

getent group invariance-swarm-infrastructure >/dev/null ||
  groupadd --system invariance-swarm-infrastructure
getent group invariance-swarm-backup-readers >/dev/null ||
  groupadd --system invariance-swarm-backup-readers
id swarm-infrastructure >/dev/null 2>&1 ||
  useradd \
    --system \
    --gid invariance-swarm-infrastructure \
    --home-dir /nonexistent \
    --shell /usr/sbin/nologin \
    swarm-infrastructure

install -d \
  -o swarm-infrastructure \
  -g invariance-swarm-infrastructure \
  -m 0700 \
  /srv/invariance/swarm/agent-workspaces/infrastructure
install -d -o root -g root -m 0755 /etc/invariance-swarm
install -d -o root -g root -m 0700 /var/lib/invariance-swarm-infrastructure
install -d -o root -g root -m 0700 /srv/invariance/postgres
for directory in backups bin certs conf init pgbouncer schema; do
  install -d -o root -g root -m 0700 \
    "/srv/invariance/postgres/${directory}"
done
for directory in archive data logs; do
  install -d -o 999 -g invariance-swarm-infrastructure -m 0750 \
    "/srv/invariance/postgres/${directory}"
done
install -d \
  -o omenka \
  -g invariance-swarm-backup-readers \
  -m 2750 \
  /srv/invariance/swarm/control-plane-runtime/backups
find /srv/invariance/swarm/control-plane-runtime/backups \
  -maxdepth 1 \
  -type f \
  -name '*.dump' \
  -exec chgrp invariance-swarm-backup-readers {} +
find /srv/invariance/swarm/control-plane-runtime/backups \
  -maxdepth 1 \
  -type f \
  -name '*.dump' \
  -exec chmod 0640 {} +
install -o omenka -g invariance -m 0750 \
  "$worker/systemd/backup-database.sh" \
  /srv/invariance/swarm/control-plane-runtime/scripts/backup-database.sh

for unit in \
  invariance-swarm-infrastructure-broker.service \
  invariance-swarm-infrastructure-worker.service
do
  install -o root -g root -m 0644 \
    "$worker/systemd/$unit" \
    "/etc/systemd/system/$unit"
  systemd-analyze verify "/etc/systemd/system/$unit"
done

for unit in \
  invariance-postgres-backup.service \
  invariance-postgres-backup.timer
do
  if [[ ! -e "/etc/systemd/system/$unit" ]]; then
    install -o root -g root -m 0644 /dev/null \
      "/etc/systemd/system/$unit"
  fi
done
install -d -o root -g root -m 0755 \
  /etc/systemd/system/timers.target.wants
ln -sfn ../invariance-postgres-backup.timer \
  /etc/systemd/system/timers.target.wants/invariance-postgres-backup.timer

systemctl daemon-reload

if $enable; then
  systemctl enable invariance-swarm-infrastructure-broker.service
  systemctl enable invariance-swarm-infrastructure-worker.service
fi
if $start; then
  systemctl start invariance-swarm-infrastructure-broker.service
  systemctl start invariance-swarm-infrastructure-worker.service
fi
if $restart; then
  systemctl restart invariance-swarm-infrastructure-broker.service
fi

printf \
  'Infrastructure units installed. enable=%s start=%s restart=%s\n' \
  "$enable" \
  "$start" \
  "$restart"
