#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this rehearsal as root.\n' >&2
  exit 1
fi

action=${1:-run}
repo=/home/omenka/Projects/swarm-control-plane
source_root=/home/omenka/Projects
state=/var/lib/invariance-swarm-rehearsal
postgres_root=/srv/invariance/postgres
source_stage=/srv/invariance/rehearsal-source
unit=invariance-postgres-rehearsal
broker_group=swarm-rehearsal
backup_group=swarm-rehearsal-bak
legacy_broker_group=invariance-swarm-rehearsal

guard_rehearsal() {
  test -f "$state/DISPOSABLE_REHEARSAL"
  test "$(cat "$state/DISPOSABLE_REHEARSAL")" = vm2-postgres
  if [[ -f $postgres_root/metadata.json ]]; then
    test "$(python3 -c \
      'import json,sys; print(json.load(open(sys.argv[1]))["deployment"])' \
      "$postgres_root/metadata.json")" = vm2-invariance-postgres
  else
    test -d "$postgres_root"
    test -z "$(find "$postgres_root" -mindepth 1 -maxdepth 1 \
      ! -type d -print -quit)"
  fi
}

cleanup() {
  guard_rehearsal
  systemctl stop invariance-postgres-backup.timer 2>/dev/null || true
  systemctl disable invariance-postgres-backup.timer 2>/dev/null || true
  if [[ -f $postgres_root/compose.yaml &&
    -f $postgres_root/.env.postgres ]]
  then
    docker compose \
      --project-directory "$postgres_root" \
      -f "$postgres_root/compose.yaml" \
      --env-file "$postgres_root/.env.postgres" \
      down --volumes --remove-orphans 2>/dev/null || true
  fi
  rm -f \
    /etc/systemd/system/invariance-postgres-backup.service \
    /etc/systemd/system/invariance-postgres-backup.timer \
    /etc/systemd/system/timers.target.wants/invariance-postgres-backup.timer
  systemctl daemon-reload
  rm -rf "$postgres_root" "$source_stage"
  groupdel "$backup_group" 2>/dev/null || true
  groupdel "$broker_group" 2>/dev/null || true
}

if [[ $action == cleanup ]]; then
  cleanup
  printf 'Disposable VM2 Postgres rehearsal removed.\n'
  exit 0
fi
if [[ $action != run ]]; then
  printf 'Usage: %s [run|cleanup]\n' "$0" >&2
  exit 2
fi

if [[ -e $postgres_root ]]; then
  printf '%s already exists; refusing to touch it.\n' "$postgres_root" >&2
  exit 1
fi
test -d "$source_root/invariance_research/.git"
test -d "$source_root/bulletproof_bt/.git"
test -d "$repo/.git"
test -S /var/run/docker.sock
if getent group "$legacy_broker_group" >/dev/null &&
  [[ ! -e $state/DISPOSABLE_REHEARSAL && ! -e $postgres_root ]]
then
  groupdel "$legacy_broker_group"
fi
if getent group "$broker_group" >/dev/null ||
  getent group "$backup_group" >/dev/null
then
  printf 'Rehearsal groups already exist; clean up the previous run first.\n' >&2
  exit 1
fi
groupadd --system "$broker_group"
groupadd --system "$backup_group"

install -d -o root -g root -m 0700 "$state"
printf 'vm2-postgres\n' > "$state/DISPOSABLE_REHEARSAL"
chmod 0600 "$state/DISPOSABLE_REHEARSAL"
install -d -o root -g root -m 0755 \
  "$state/control-plane-runtime/backups" \
  "$source_stage"
git clone --quiet --local --no-hardlinks \
  "$source_root/invariance_research" "$source_stage/invariance_research"
git clone --quiet --local --no-hardlinks \
  "$source_root/bulletproof_bt" "$source_stage/bulletproof_bt"
git clone --quiet --local --no-hardlinks \
  "$repo" "$source_stage/swarm-control-plane"
python3 -m venv "$state/.venv"
"$state/.venv/bin/python" -m pip install --quiet --upgrade pip
"$state/.venv/bin/python" -m pip install --quiet \
  -e "$source_stage/swarm-control-plane/worker"

install -d -o root -g root -m 0700 "$postgres_root"
for directory in backups bin certs conf init pgbouncer schema; do
  install -d -o root -g root -m 0700 "$postgres_root/$directory"
done
for directory in archive data logs; do
  install -d -o 999 -g "$broker_group" -m 0750 \
    "$postgres_root/$directory"
done

for target in \
  /etc/systemd/system/invariance-postgres-backup.service \
  /etc/systemd/system/invariance-postgres-backup.timer
do
  install -o root -g root -m 0644 /dev/null "$target"
done
install -d -o root -g root -m 0755 \
  /etc/systemd/system/timers.target.wants
ln -sfn ../invariance-postgres-backup.timer \
  /etc/systemd/system/timers.target.wants/invariance-postgres-backup.timer

set +e
systemd-run \
  --unit="$unit" \
  --wait \
  --pipe \
  --collect \
  --property=Type=oneshot \
  --property=User=root \
  --property="Group=$broker_group" \
  --property="SupplementaryGroups=$backup_group" \
  --property=NoNewPrivileges=yes \
  --property=PrivateTmp=yes \
  --property=ProtectSystem=strict \
  --property=ProtectHome=yes \
  --property=ProtectKernelTunables=yes \
  --property=ProtectKernelModules=yes \
  --property=ProtectKernelLogs=yes \
  --property=ProtectControlGroups=yes \
  --property=ProtectClock=yes \
  --property=ProtectHostname=yes \
  --property=RestrictRealtime=yes \
  --property=RestrictSUIDSGID=yes \
  --property=LockPersonality=yes \
  --property=MemoryDenyWriteExecute=yes \
  --property=CapabilityBoundingSet= \
  --property='RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6' \
  --property=RuntimeDirectory=invariance-swarm-infrastructure \
  --property=RuntimeDirectoryMode=0750 \
  --property="ReadOnlyPaths=$source_stage" \
  --property="ReadWritePaths=$state" \
  --property="ReadWritePaths=$postgres_root" \
  --property=ReadWritePaths=/etc/systemd/system/invariance-postgres-backup.service \
  --property=ReadWritePaths=/etc/systemd/system/invariance-postgres-backup.timer \
  "$state/.venv/bin/python" \
  "$source_stage/swarm-control-plane/worker/scripts/rehearse_postgres_runbook.py"
status=$?
set -e

cat "$state/report.json"
printf 'Rehearsal resources were preserved for inspection.\n'
printf 'Cleanup: sudo %s cleanup\n' "$0"
exit "$status"
