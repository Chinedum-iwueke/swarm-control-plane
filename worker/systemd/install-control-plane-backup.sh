#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

repo=/srv/invariance/swarm/repositories/swarm-control-plane
worker="$repo/worker"
runtime=/srv/invariance/swarm/control-plane-runtime

test -f "$runtime/compose.yaml"
test -S /var/run/docker.sock
getent group invariance-swarm-backup-readers >/dev/null ||
  groupadd --system invariance-swarm-backup-readers
install -d -o root -g invariance-swarm-backup-readers -m 2750 \
  "$runtime/backups"
install -d -o root -g root -m 0755 "$runtime/scripts" /run/invariance-swarm

python3 -m venv --clear /opt/invariance-swarm-worker
/opt/invariance-swarm-worker/bin/pip install --disable-pip-version-check "$worker"
install -o root -g invariance-swarm-backup-readers -m 0750 \
  "$worker/systemd/backup-database.sh" "$runtime/scripts/backup-database.sh"
for unit in \
  invariance-swarm-control-plane-backup.service \
  invariance-swarm-control-plane-backup.timer \
  invariance-swarm-control-plane-restore-drill.service \
  invariance-swarm-control-plane-restore-drill.timer; do
  install -o root -g root -m 0644 "$worker/systemd/$unit" "/etc/systemd/system/$unit"
  systemd-analyze verify "/etc/systemd/system/$unit"
done
systemctl daemon-reload

case ${1:-} in
  --enable)
    systemctl enable --now \
      invariance-swarm-control-plane-backup.timer \
      invariance-swarm-control-plane-restore-drill.timer
    ;;
  "") ;;
  *) echo "Usage: $0 [--enable]" >&2; exit 2 ;;
esac
echo "Control-plane backup units installed."
