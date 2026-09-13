#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi

expected_hostname="exec2-lagos.invarianceresearch.xyz"
if [[ "$(hostnamectl --static)" != "$expected_hostname" ]]; then
  echo "EXEC2 hostname must be $expected_hostname." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  ca-certificates \
  chrony \
  curl \
  docker.io \
  docker-compose-v2 \
  fail2ban \
  git \
  jq \
  python3 \
  python3-venv \
  sqlite3 \
  unattended-upgrades \
  ufw

systemctl enable --now chrony docker fail2ban unattended-upgrades

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

if ! swapon --show=NAME --noheadings | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 0600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
fi

ufw default deny incoming
ufw default allow outgoing
if ! ip link show tailscale0 >/dev/null 2>&1; then
  echo "EXEC2 must join Tailscale before firewall admission." >&2
  exit 1
fi
ufw allow in on tailscale0 to any port 22 proto tcp
while ufw status | grep -Eq '^22/tcp[[:space:]].*ALLOW IN'; do
  ufw --force delete allow 22/tcp
done
while ufw status | grep -Eq '^OpenSSH[[:space:]].*ALLOW IN'; do
  ufw --force delete allow OpenSSH
done
ufw --force enable

egress_ip="$(curl -4fsS --max-time 15 https://api.ipify.org)"
egress_country="$(curl -4fsS --max-time 15 https://ipinfo.io/country | tr -d '[:space:]')"
if [[ "$egress_country" != "NG" ]]; then
  echo "EXEC2 egress must resolve to Nigeria; observed $egress_country." >&2
  exit 1
fi

declare -A venue_status
for venue in \
  bybit_main=https://api.bybit.com/v5/market/time \
  bybit_demo=https://api-demo.bybit.com/v5/market/time \
  binance_spot=https://api.binance.com/api/v3/time \
  binance_futures=https://fapi.binance.com/fapi/v1/time; do
  name="${venue%%=*}"
  url="${venue#*=}"
  status="$(curl -4sS -o /dev/null --max-time 15 -w '%{http_code}' "$url")"
  if [[ "$status" != "200" ]]; then
    echo "$name preflight failed with HTTP $status." >&2
    exit 1
  fi
  venue_status["$name"]="$status"
done

python3 - "$egress_ip" "$egress_country" \
  "${venue_status[bybit_main]}" "${venue_status[bybit_demo]}" \
  "${venue_status[binance_spot]}" "${venue_status[binance_futures]}" <<'PY'
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

state = {
    "schema_version": "exec2-lagos-host-foundation-v1.0.0",
    "machine": "exec2-lagos",
    "hostname": platform.node(),
    "processor_count": os.cpu_count(),
    "observed_at": datetime.now(UTC).isoformat(),
    "egress_ip": sys.argv[1],
    "egress_country": sys.argv[2],
    "venue_preflight": {
        "bybit_main": int(sys.argv[3]),
        "bybit_demo": int(sys.argv[4]),
        "binance_spot": int(sys.argv[5]),
        "binance_futures": int(sys.argv[6]),
    },
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

echo "EXEC2 Lagos host foundation installed without capital or order authority."
