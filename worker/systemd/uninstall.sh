#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="invariance-swarm-worker.service"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"

stop_service=false
disable_service=false

usage() {
  cat <<'EOF'
Usage: uninstall.sh [--stop] [--disable]

Removes the systemd unit and reloads systemd. Running/enabled state is changed
only when the corresponding explicit flag is supplied. Credentials,
workspaces, logs, and repositories are never deleted.
EOF
}

while (($#)); do
  case "$1" in
    --stop)
      stop_service=true
      ;;
    --disable)
      disable_service=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ((EUID != 0)); then
  printf 'uninstall.sh must run as root.\n' >&2
  exit 1
fi

if [[ "${stop_service}" == true ]]; then
  systemctl stop "${UNIT_NAME}"
fi
if [[ "${disable_service}" == true ]]; then
  systemctl disable "${UNIT_NAME}"
fi

rm -f -- "${UNIT_PATH}"
systemctl daemon-reload

printf 'Removed %s.\n' "${UNIT_PATH}"
printf 'Credentials, workspaces, logs, and repositories were preserved.\n'
