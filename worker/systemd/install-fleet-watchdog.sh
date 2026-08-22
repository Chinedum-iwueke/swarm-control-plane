#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file=/etc/invariance-swarm/fleet-watchdog.env
test -f "$env_file" || { echo "Missing $env_file" >&2; exit 1; }
grep -q '^SWARM_WATCHDOG_TARGETS=' "$env_file"
grep -q '^SWARM_WATCHDOG_TELEGRAM_TOKEN_FILE=' "$env_file"

getent group invariance-fleet-watchdog >/dev/null || groupadd --system invariance-fleet-watchdog
id invariance-fleet-watchdog >/dev/null 2>&1 || useradd --system --gid invariance-fleet-watchdog --home-dir /nonexistent --shell /usr/sbin/nologin invariance-fleet-watchdog
install -d -o invariance-fleet-watchdog -g invariance-fleet-watchdog -m 0700 /var/lib/invariance-swarm-fleet-watchdog
python3 -m venv --clear /opt/invariance-swarm-worker
/opt/invariance-swarm-worker/bin/pip install --disable-pip-version-check "$repo"
install -o root -g root -m 0644 "$repo/systemd/invariance-swarm-fleet-watchdog.service" /etc/systemd/system/invariance-swarm-fleet-watchdog.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/invariance-swarm-fleet-watchdog.service

if [[ ${1:-} == "--enable" ]]; then
  systemctl enable --now invariance-swarm-fleet-watchdog.service
fi
echo "Independent fleet watchdog installed."
