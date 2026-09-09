#!/usr/bin/env bash
set -euo pipefail

unit=invariance-swarm-alpha-research-executor.service
root=/home/omenka/Projects/swarm-control-plane/worker
source_unit="$root/systemd/$unit"
destination=/etc/systemd/system/$unit
environment=/etc/invariance-swarm/alpha002-executor.env
repository=/home/omenka/Projects/bulletproof_bt
workspace=/home/omenka/Projects/swarm-agent-workspaces
enable=false
start=false

while (($#)); do
  case "$1" in
    --enable) enable=true ;;
    --start) start=true ;;
    *) printf 'Usage: %s [--enable] [--start]\n' "$0" >&2; exit 2 ;;
  esac
  shift
done

((EUID == 0)) || { printf 'Installer must run as root.\n' >&2; exit 1; }
test -f "$source_unit"
test -x "$root/.venv/bin/invariance-swarm-worker"
test -x "$repository/.venv/bin/python"
test -f "$environment"
test "$(stat -c '%U:%G:%a' "$environment")" = root:root:600
test "$(git -C "$repository" rev-parse --show-toplevel)" = "$repository"
test ! -L "$repository"
test ! -L "$workspace"

install -d -o omenka -g omenka -m 0700 "$workspace"
install -d -o omenka -g omenka -m 0700 /home/omenka/.local/state/invariance-swarm
install -d -o omenka -g omenka -m 0700 /home/omenka/.local/share/invariance-swarm/alpha002-bundles
install -d -o omenka -g omenka -m 0700 "$repository/.git/worktrees"
systemd-analyze verify "$source_unit"
install -o root -g root -m 0644 "$source_unit" "$destination"
systemctl daemon-reload
[[ "$enable" == true ]] && systemctl enable "$unit"
[[ "$start" == true ]] && systemctl restart "$unit"
printf 'Alpha scientific executor installed. enable=%s start=%s\n' "$enable" "$start"
