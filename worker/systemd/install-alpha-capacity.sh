#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" -eq 0 || { echo 'Run with sudo bash.' >&2; exit 1; }
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
native=/home/omenka/Projects/bulletproof_bt
for file in "$native/scripts/queue_alpha_capacity_assignment.py" "$native/scripts/run_alpha_capacity_job.py" "$native/.venv/bin/python"; do
  test -f "$file" || { echo "Required native capacity implementation missing: $file" >&2; exit 1; }
done
for slot in 1 2; do
  file="/etc/invariance-swarm/alpha-capacity-executor-$slot.env"
  test -f "$file" || { echo "Register executor slot $slot first: $file" >&2; exit 1; }
  test "$(stat -c '%u:%a' "$file")" = '0:600' || { echo "Require root-owned mode 600: $file" >&2; exit 1; }
done
slug1="$(sed -n 's/^SWARM_AGENT_SLUG=//p' /etc/invariance-swarm/alpha-capacity-executor-1.env)"
slug2="$(sed -n 's/^SWARM_AGENT_SLUG=//p' /etc/invariance-swarm/alpha-capacity-executor-2.env)"
test "$slug1" = vm1-alpha-research-executor-v2
test "$slug2" = vm1-alpha-research-executor-capacity-2
install -d -o omenka -g omenka -m 0700 /home/omenka/.local/state/invariance-swarm
test -f /etc/invariance-swarm/alpha-capacity.yaml || install -o root -g root -m 0644 "$source_dir/alpha-capacity.sample.yaml" /etc/invariance-swarm/alpha-capacity.yaml
install -o root -g root -m 0644 "$source_dir/invariance-swarm-alpha-capacity-director.service" /etc/systemd/system/
install -o root -g root -m 0644 "$source_dir/invariance-swarm-alpha-capacity-executor@.service" /etc/systemd/system/
systemctl daemon-reload
# Retire the old consumer before permitting the two separately registered slots.
systemctl disable --now invariance-swarm-alpha-research-executor-v2.service
systemctl enable --now invariance-swarm-alpha-capacity-director.service
systemctl enable --now invariance-swarm-alpha-capacity-executor@1.service invariance-swarm-alpha-capacity-executor@2.service
echo 'Native capacity director and two governed executor slots installed.'
