#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 0 || { echo 'Run with sudo bash.' >&2; exit 1; }
test "$#" -eq 2 || {
  echo "usage: $0 <exact-control-plane-commit> <exact-bulletproof-source-commit>" >&2
  exit 1
}

control_commit="$1"
source_commit="$2"
for commit in "$control_commit" "$source_commit"; do
case "$commit" in
  *[!0-9a-f]*|'') echo 'Source commits must be lowercase hexadecimal.' >&2; exit 1 ;;
esac
test "${#commit}" -eq 40 -o "${#commit}" -eq 64 || {
  echo 'Source commits must be full Git commits.' >&2
  exit 1
}
done

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
native=/home/omenka/Projects/bulletproof_bt-production
data_root=/home/omenka/Projects/bulletproof_bt/research_data
control=/home/omenka/Projects/swarm-control-plane
for file in \
  "$native/scripts/replenish_disc010_signal_screens.py" \
  "$native/scripts/queue_disc010_signal_screen.py" \
  "$native/scripts/run_disc010_signal_screen.py" \
  "$native/scripts/run_alpha_capacity_job.py" \
  "$control/worker/scripts/disc010_publish.py" \
  "$control/worker/.venv/bin/python" \
  /home/omenka/Projects/bulletproof_bt/.venv/bin/python \
  "$data_root/manifests/coverage.parquet"; do
  test -f "$file" || { echo "Required DISC-010 dependency missing: $file" >&2; exit 1; }
done
test "$(git -C "$control" rev-parse HEAD)" = "$control_commit" || {
  echo 'Production control-plane checkout does not match the pinned source commit.' >&2
  exit 1
}
test "$(git -C "$native" rev-parse HEAD)" = "$source_commit" || {
  echo 'Production Bulletproof checkout does not match the pinned source commit.' >&2
  exit 1
}
source /etc/invariance-swarm/pilot-operator.env
test -n "${SWARM_API_URL:-}" -a -n "${SWARM_ORCHESTRATOR_TOKEN:-}" || {
  echo 'Pilot operator API URL and token are required for canonical publication.' >&2
  exit 1
}

install -d -o root -g root -m 0755 /etc/invariance-swarm
install -d -o omenka -g omenka -m 0700 \
  /home/omenka/.local/state/invariance-swarm/disc010 \
  /home/omenka/.local/state/invariance-swarm/disc010/runs
environment="$(mktemp)"
trap 'rm -f "$environment"' EXIT
printf 'DISC010_SOURCE_COMMIT=%s\n' "$source_commit" > "$environment"
install -o root -g root -m 0600 \
  "$environment" /etc/invariance-swarm/disc010-replenisher.env
printf '%s\n' "$SWARM_API_URL" | install -o root -g root -m 0600 \
  /dev/stdin /etc/invariance-swarm/disc010-api-url
printf '%s\n' "$SWARM_ORCHESTRATOR_TOKEN" | install -o root -g root -m 0600 \
  /dev/stdin /etc/invariance-swarm/disc010-orchestrator.token
install -o root -g root -m 0644 \
  "$source_dir/invariance-swarm-disc010-replenisher.service" \
  "$source_dir/invariance-swarm-disc010-replenisher.timer" \
  "$source_dir/invariance-swarm-disc010-publisher.service" \
  "$source_dir/invariance-swarm-disc010-publisher.timer" \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now \
  invariance-swarm-disc010-replenisher.timer \
  invariance-swarm-disc010-publisher.timer
systemctl start invariance-swarm-disc010-replenisher.service
systemctl start invariance-swarm-disc010-publisher.service
echo 'DISC-010 replenishment and canonical publication installed and started.'
