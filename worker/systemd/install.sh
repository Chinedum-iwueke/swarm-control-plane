#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="invariance-swarm-worker.service"
UNIT_DESTINATION="/etc/systemd/system/${UNIT_NAME}"
REPOSITORY_ROOT="/home/omenka/Projects"
WORKER_ROOT="${REPOSITORY_ROOT}/swarm-control-plane/worker"
WORKSPACE_ROOT="${REPOSITORY_ROOT}/swarm-agent-workspaces"
ENVIRONMENT_FILE="/etc/invariance-swarm/vm1-worker.env"
WORKER_EXECUTABLE="${WORKER_ROOT}/.venv/bin/invariance-swarm-worker"
APPROVED_REPOSITORIES=(
  "swarm-control-plane"
  "bulletproof_bt"
  "invariance_research"
)

SCRIPT_DIRECTORY="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
  pwd
)"
UNIT_SOURCE="${SCRIPT_DIRECTORY}/${UNIT_NAME}"

enable_service=false
start_service=false

usage() {
  cat <<'EOF'
Usage: install.sh [--enable] [--start]

Installs the worker unit and reloads systemd. The service is not enabled or
started unless the corresponding explicit flag is supplied.
EOF
}

while (($#)); do
  case "$1" in
    --enable)
      enable_service=true
      ;;
    --start)
      start_service=true
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
  printf 'install.sh must run as root.\n' >&2
  exit 1
fi

if [[ ! -f "${UNIT_SOURCE}" ]]; then
  printf 'Unit file is missing: %s\n' "${UNIT_SOURCE}" >&2
  exit 1
fi
if [[ ! -x "${WORKER_EXECUTABLE}" ]]; then
  printf 'Worker executable is missing: %s\n' "${WORKER_EXECUTABLE}" >&2
  exit 1
fi
if [[ ! -f "${ENVIRONMENT_FILE}" ]]; then
  printf 'Environment file is missing: %s\n' "${ENVIRONMENT_FILE}" >&2
  exit 1
fi
environment_owner="$(stat -c '%u' "${ENVIRONMENT_FILE}")"
environment_mode="$(stat -c '%a' "${ENVIRONMENT_FILE}")"
if [[ "${environment_owner}" != 0 ]]; then
  printf 'Environment file must be owned by root: %s\n' \
    "${ENVIRONMENT_FILE}" >&2
  exit 1
fi
if ((8#${environment_mode} & 8#077)); then
  printf 'Environment file must not allow group or other access: %s\n' \
    "${ENVIRONMENT_FILE}" >&2
  exit 1
fi
if ! id -u omenka >/dev/null 2>&1; then
  printf 'Required user does not exist: omenka\n' >&2
  exit 1
fi

for repository in "${APPROVED_REPOSITORIES[@]}"; do
  repository_path="${REPOSITORY_ROOT}/${repository}"
  if [[ -L "${repository_path}" ]]; then
    printf 'Approved repository must not be a symlink: %s\n' \
      "${repository_path}" >&2
    exit 1
  fi
  if [[ ! -d "${repository_path}/.git" ]]; then
    printf 'Approved Git repository is missing: %s\n' \
      "${repository_path}" >&2
    exit 1
  fi
  git_root="$(git -C "${repository_path}" rev-parse --show-toplevel)"
  if [[ "${git_root}" != "${repository_path}" ]]; then
    printf 'Repository path is not its Git root: %s\n' \
      "${repository_path}" >&2
    exit 1
  fi
done

systemd-analyze verify "${UNIT_SOURCE}"

if [[ -L "${WORKSPACE_ROOT}" ]]; then
  printf 'Workspace root must not be a symlink: %s\n' \
    "${WORKSPACE_ROOT}" >&2
  exit 1
fi
install -d -o omenka -g omenka -m 0700 "${WORKSPACE_ROOT}"
for repository in "${APPROVED_REPOSITORIES[@]}"; do
  install -d -o omenka -g omenka -m 0700 \
    "${REPOSITORY_ROOT}/${repository}/.git/worktrees"
done

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
  printf 'The service was not enabled or started.\n'
fi
