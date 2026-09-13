#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

expected_hostname="exec1.invarianceresearch.xyz"
if [[ "$(hostnamectl --static)" != "$expected_hostname" ]]; then
  echo "EXEC1 hostname must be $expected_hostname." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  ca-certificates \
  chrony \
  curl \
  fail2ban \
  git \
  jq \
  python3 \
  python3-venv \
  sqlite3 \
  unattended-upgrades \
  ufw

getent group invariance-execution >/dev/null || groupadd --system invariance-execution
id swarm-execution >/dev/null 2>&1 || useradd \
  --system \
  --gid invariance-execution \
  --home-dir /var/lib/invariance-execution \
  --create-home \
  --shell /usr/sbin/nologin \
  swarm-execution

install -d -o root -g root -m 0755 /srv/invariance/swarm/repositories
install -d -o root -g invariance-execution -m 0750 /etc/invariance-swarm/execution
install -d -o swarm-execution -g invariance-execution -m 0700 \
  /var/lib/invariance-execution/artifacts \
  /var/lib/invariance-execution/state

systemctl enable --now chrony fail2ban unattended-upgrades
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

if ! swapon --show=NAME --noheadings | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 0600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
fi

python3 - <<'PY'
import json
import os
import platform
from pathlib import Path

state = {
    "schema_version": "exec1-host-foundation-v1.0.0",
    "machine": "exec1-execution",
    "hostname": platform.node(),
    "processor_count": os.cpu_count(),
    "capital_authority": False,
    "order_authority": False,
    "venue_credentials_installed": False,
    "execution_runtime_enabled": False,
}
path = Path("/var/lib/invariance-execution/host-foundation.json")
path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
chown swarm-execution:invariance-execution \
  /var/lib/invariance-execution/host-foundation.json

echo "EXEC1 host foundation installed without capital or order authority."
