#!/usr/bin/env bash
set -euo pipefail

unit="hermes-telegram-gateway.service"
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="/srv/invariance/swarm/repositories/swarm-control-plane/telegram-gateway"
environment="/etc/invariance-swarm/telegram-gateway.env"
bot_token="/etc/invariance-swarm/telegram-bot.token"
channel_token="/etc/invariance-swarm/founder-channel.token"

if ((EUID != 0)); then
  printf 'install.sh must run as root.\n' >&2
  exit 1
fi
for path in "${environment}" "${bot_token}" "${channel_token}"; do
  if [[ ! -f "${path}" || "$(stat -c '%u' "${path}")" != 0 ]]; then
    printf 'Required root-owned file is missing: %s\n' "${path}" >&2
    exit 1
  fi
  mode="$(stat -c '%a' "${path}")"
  if ((8#${mode} & 8#077)); then
    printf 'Protected file has unsafe permissions: %s\n' "${path}" >&2
    exit 1
  fi
done
if ! id swarm-telegram >/dev/null 2>&1; then
  useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin \
    swarm-telegram
fi
if [[ ! -x "${root}/.venv/bin/hermes-telegram-gateway" ]]; then
  printf 'Gateway virtual environment is unavailable.\n' >&2
  exit 1
fi
install -d -o swarm-telegram -g swarm-telegram -m 0700 \
  /srv/invariance/swarm/telegram-gateway
systemd-analyze verify "${source_dir}/${unit}"
install -o root -g root -m 0644 \
  "${source_dir}/${unit}" "/etc/systemd/system/${unit}"
systemctl daemon-reload
printf 'Installed %s without enabling or starting it.\n' "${unit}"
