#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 0 || { echo 'Run with sudo bash.' >&2; exit 1; }
test "$#" -eq 1 || { echo "usage: $0 <exact-bulletproof-source-commit>" >&2; exit 1; }

source_commit="$1"
case "$source_commit" in
  *[!0-9a-f]*|'') echo 'Source commit must be lowercase hexadecimal.' >&2; exit 1 ;;
esac
test "${#source_commit}" -eq 40 -o "${#source_commit}" -eq 64 || {
  echo 'Source commit must be a full Git commit.' >&2
  exit 1
}

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
native=/home/omenka/Projects/bulletproof_bt-production
data_root=/home/omenka/Projects/bulletproof_bt/research_data
for file in \
  "$native/scripts/replenish_disc010_signal_screens.py" \
  "$native/scripts/queue_disc010_signal_screen.py" \
  "$native/scripts/run_disc010_signal_screen.py" \
  "$native/scripts/run_alpha_capacity_job.py" \
  /home/omenka/Projects/bulletproof_bt/.venv/bin/python \
  "$data_root/manifests/coverage.parquet"; do
  test -f "$file" || { echo "Required DISC-010 dependency missing: $file" >&2; exit 1; }
done
test "$(git -C "$native" rev-parse HEAD)" = "$source_commit" || {
  echo 'Production Bulletproof checkout does not match the pinned source commit.' >&2
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
install -o root -g root -m 0644 \
  "$source_dir/invariance-swarm-disc010-replenisher.service" \
  "$source_dir/invariance-swarm-disc010-replenisher.timer" \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now invariance-swarm-disc010-replenisher.timer
systemctl start invariance-swarm-disc010-replenisher.service
echo 'DISC-010 bounded signal-screen replenisher installed and started.'

