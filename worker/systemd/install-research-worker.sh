#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME=invariance-swarm-research-worker.service
WORKER_ROOT=/home/omenka/Projects/swarm-control-plane/worker
UNIT_SOURCE="$WORKER_ROOT/systemd/$UNIT_NAME"
UNIT_DESTINATION="/etc/systemd/system/$UNIT_NAME"
ENVIRONMENT_FILE=/etc/invariance-swarm/vm1-research-worker.env
WORKSPACE_ROOT=/home/omenka/Projects/swarm-agent-workspaces
REPOSITORY=/home/omenka/Projects/bulletproof_bt
WORKER_EXECUTABLE="$WORKER_ROOT/.venv/bin/invariance-swarm-worker"

enable_service=false
start_service=false

usage() {
  cat <<'EOF'
Usage: install-research-worker.sh [--enable] [--start]

Install the restricted VM1 research-runner unit. The unit is not enabled or
started unless the corresponding explicit flag is supplied.
EOF
}

while (($#)); do
  case "$1" in
    --enable) enable_service=true ;;
    --start) start_service=true ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ((EUID != 0)); then
  printf 'install-research-worker.sh must run as root.\n' >&2
  exit 1
fi

test -f "$UNIT_SOURCE"
test -x "$WORKER_EXECUTABLE"
test -f "$ENVIRONMENT_FILE"
test -d "$REPOSITORY/.git"

environment_owner="$(stat -c '%u' "$ENVIRONMENT_FILE")"
environment_mode="$(stat -c '%a' "$ENVIRONMENT_FILE")"
if [[ "$environment_owner" != 0 ]]; then
  printf 'Environment file must be owned by root: %s\n' "$ENVIRONMENT_FILE" >&2
  exit 1
fi
if ((8#$environment_mode & 8#077)); then
  printf 'Environment file must not allow group or other access: %s\n' \
    "$ENVIRONMENT_FILE" >&2
  exit 1
fi
if [[ -L "$REPOSITORY" || -L "$WORKSPACE_ROOT" ]]; then
  printf 'Repository and workspace roots must not be symlinks.\n' >&2
  exit 1
fi
if [[ "$(git -C "$REPOSITORY" rev-parse --show-toplevel)" != "$REPOSITORY" ]]; then
  printf 'Repository path is not its Git root: %s\n' "$REPOSITORY" >&2
  exit 1
fi

install -d -o omenka -g omenka -m 0700 "$WORKSPACE_ROOT"
install -d -o omenka -g omenka -m 0700 "$REPOSITORY/.git/worktrees"
systemd-analyze verify "$UNIT_SOURCE"
install -o root -g root -m 0644 "$UNIT_SOURCE" "$UNIT_DESTINATION"
systemctl daemon-reload

if [[ "$enable_service" == true ]]; then
  systemctl enable "$UNIT_NAME"
fi
if [[ "$start_service" == true ]]; then
  systemctl start "$UNIT_NAME"
fi

printf 'Installed %s. enable=%s start=%s\n' \
  "$UNIT_DESTINATION" "$enable_service" "$start_service"
