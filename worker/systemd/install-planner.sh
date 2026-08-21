#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="invariance-swarm-founder-planner.service"
UNIT_DESTINATION="/etc/systemd/system/${UNIT_NAME}"
WORKER_ROOT="/home/omenka/Projects/swarm-control-plane/worker"
EXECUTABLE="${WORKER_ROOT}/.venv/bin/invariance-swarm-founder-planner"
ENVIRONMENT_FILE="/etc/invariance-swarm/vm1-founder-planner.env"
WORKSPACE="/home/omenka/Projects/swarm-agent-workspaces/founder-intake"
CODEX_HOME="/etc/invariance-swarm/codex-planner"

SCRIPT_DIRECTORY="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
  pwd
)"
UNIT_SOURCE="${SCRIPT_DIRECTORY}/${UNIT_NAME}"

enable_service=false
start_service=false
while (($#)); do
  case "$1" in
    --enable) enable_service=true ;;
    --start) start_service=true ;;
    -h|--help)
      printf 'Usage: install-planner.sh [--enable] [--start]\n'
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

if ((EUID != 0)); then
  printf 'install-planner.sh must run as root.\n' >&2
  exit 1
fi
if [[ ! -f "${UNIT_SOURCE}" || ! -x "${EXECUTABLE}" ]]; then
  printf 'Planner unit or executable is unavailable.\n' >&2
  exit 1
fi
if [[ ! -f "${ENVIRONMENT_FILE}" ]]; then
  printf 'Planner environment is unavailable: %s\n' "${ENVIRONMENT_FILE}" >&2
  exit 1
fi
if [[ "$(stat -c '%u' "${ENVIRONMENT_FILE}")" != 0 ]]; then
  printf 'Planner environment must be root-owned.\n' >&2
  exit 1
fi
environment_mode="$(stat -c '%a' "${ENVIRONMENT_FILE}")"
if ((8#${environment_mode} & 8#077)); then
  printf 'Planner environment must not allow group or other access.\n' >&2
  exit 1
fi
if [[ ! -d "${CODEX_HOME}" ]]; then
  printf 'The dedicated planner Codex home is unavailable: %s\n' "${CODEX_HOME}" >&2
  exit 1
fi
if ! runuser -u omenka -- env \
  CODEX_HOME="${CODEX_HOME}" \
  /usr/bin/codex login status >/dev/null; then
  printf 'The dedicated planner Codex home is not authenticated.\n' >&2
  exit 1
fi

install -d -o omenka -g omenka -m 0700 "${WORKSPACE}"
systemd-analyze verify "${UNIT_SOURCE}"
install -o root -g root -m 0644 "${UNIT_SOURCE}" "${UNIT_DESTINATION}"
systemctl daemon-reload

if [[ "${enable_service}" == true ]]; then
  systemctl enable "${UNIT_NAME}"
fi
if [[ "${start_service}" == true ]]; then
  systemctl start "${UNIT_NAME}"
fi
printf 'Installed %s.\n' "${UNIT_DESTINATION}"
if [[ "${enable_service}" != true && "${start_service}" != true ]]; then
  printf 'The planner service was not enabled or started.\n'
fi
