#!/usr/bin/env bash
set -euo pipefail
((EUID == 0)) || { printf 'Run with sudo bash.\n' >&2; exit 1; }
start=false
case "${1:-}" in
  '') ;;
  --start) start=true ;;
  *) printf 'Usage: %s [--start]\n' "$0" >&2; exit 2 ;;
esac
root=/home/omenka/Projects/swarm-control-plane/worker
unit=invariance-swarm-alpha-reviewer@.service
test -x "$root/.venv/bin/invariance-swarm-worker"
test -x /usr/bin/codex
test -f /etc/invariance-swarm/codex-worker/auth.json
for role in spec causality; do
  environment="/etc/invariance-swarm/alpha-${role}-reviewer.env"
  test ! -L "$environment"
  test -f "$environment"
  test "$(stat -c '%U:%G:%a' "$environment")" = root:root:600
  test "$(sed -n 's/^SWARM_AGENT_SLUG=//p' "$environment")" = "vm1-alpha-${role}-reviewer"
  runtime="/var/lib/invariance-swarm/codex-${role}-reviewer-runtime"
  test ! -L "$runtime"
  test ! -L "$runtime/auth.json"
done
systemd-analyze verify "$root/systemd/$unit"
for role in spec causality; do
  runtime="/var/lib/invariance-swarm/codex-${role}-reviewer-runtime"
  install -d -o omenka -g omenka -m 0700 "$runtime"
  if [[ ! -e "$runtime/auth.json" ]]; then
    install -o root -g root -m 0600 /dev/null "$runtime/auth.json"
  fi
done
install -d -o omenka -g omenka -m 0700 /home/omenka/Projects/swarm-agent-workspaces
install -o root -g root -m 0644 "$root/systemd/$unit" "/etc/systemd/system/$unit"
systemctl daemon-reload
if $start; then
  systemctl enable --now invariance-swarm-alpha-reviewer@spec.service invariance-swarm-alpha-reviewer@causality.service
fi
printf 'Independent reviewer units installed. start=%s; no scientific receipt is inferred.\n' "$start"
