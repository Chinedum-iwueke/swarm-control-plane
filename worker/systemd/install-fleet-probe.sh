#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file=/etc/invariance-swarm/fleet-probe.env
test -f "$env_file" || { echo "Missing $env_file" >&2; exit 1; }
grep -q '^SWARM_FLEET_MACHINE=' "$env_file"
grep -q '^SWARM_FLEET_AGENT_TOKEN_FILE=' "$env_file"

getent group invariance-fleet-probe >/dev/null || groupadd --system invariance-fleet-probe
id invariance-fleet-probe >/dev/null 2>&1 || useradd --system --gid invariance-fleet-probe --home-dir /nonexistent --shell /usr/sbin/nologin invariance-fleet-probe
install -d -o invariance-fleet-probe -g invariance-fleet-probe -m 0700 /var/lib/invariance-swarm-fleet-probe
python3 -m venv --clear /opt/invariance-swarm-worker
/opt/invariance-swarm-worker/bin/pip install --disable-pip-version-check "$repo"
install -o root -g root -m 0644 "$repo/systemd/invariance-swarm-fleet-probe.service" /etc/systemd/system/invariance-swarm-fleet-probe.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/invariance-swarm-fleet-probe.service

if [[ ${1:-} == "--enable" ]]; then
  systemctl enable --now invariance-swarm-fleet-probe.service
fi
echo "Fleet probe installed."
