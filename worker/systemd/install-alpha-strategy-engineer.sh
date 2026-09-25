#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 0 || {
  echo "Run with sudo bash." >&2
  exit 1
}

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
environment=/etc/invariance-swarm/alpha-strategy-engineer.env
test -f "$environment" || {
  echo "Register the alpha strategy engineer first: $environment" >&2
  exit 1
}
test "$(stat -c '%u:%a' "$environment")" = 0:600 || {
  echo "Require root-owned mode 600: $environment" >&2
  exit 1
}
test "$(sed -n 's/^SWARM_AGENT_SLUG=//p' "$environment")" = \
  vm1-alpha-strategy-engineer
test -f /etc/invariance-swarm/codex-worker/auth.json

bulletproof_repo=/home/omenka/Projects/bulletproof_bt
bulletproof_venv="$bulletproof_repo/.venv"
bulletproof_lock="$bulletproof_repo/requirements/dev-py311.lock"
command -v python3.11 >/dev/null || {
  echo "Python 3.11 is required for the pinned Bulletproof runtime." >&2
  exit 1
}
test -f "$bulletproof_lock" || {
  echo "Missing pinned Bulletproof validation lock: $bulletproof_lock" >&2
  exit 1
}
if [[ ! -x "$bulletproof_venv/bin/python" ]]; then
  runuser -u omenka -- python3.11 -m venv "$bulletproof_venv"
fi
runuser -u omenka -- "$bulletproof_venv/bin/python" -m pip install \
  --requirement "$bulletproof_lock"
runuser -u omenka -- "$bulletproof_venv/bin/python" - <<'PY'
import jsonschema
import numpy
import pandas
import pyarrow
import pytest
import yaml

print("bulletproof-validation-runtime=ready")
PY

runtime=/var/lib/invariance-swarm/codex-discovery-runtime
test ! -L "$runtime"
install -d -o omenka -g omenka -m 0700 "$runtime"
test ! -L "$runtime/auth.json"
if [[ ! -s "$runtime/auth.json" ]]; then
  install -o omenka -g omenka -m 0600 \
    /etc/invariance-swarm/codex-worker/auth.json "$runtime/auth.json"
fi
chown omenka:omenka "$runtime/auth.json"
chmod 0600 "$runtime/auth.json"
install -o root -g root -m 0600 "$source_dir/codex-discovery-runtime.env" \
  /etc/invariance-swarm/codex-discovery-runtime.env

install -d -o omenka -g omenka -m 0700 \
  /home/omenka/.local/state/invariance-swarm/alpha-loop-rehearsal \
  /home/omenka/Projects/swarm-agent-workspaces

probe_unit="invariance-swarm-alpha-loop-rehearsal-$(date +%s)"
systemd-run \
  --unit="$probe_unit" \
  --collect \
  --wait \
  --pipe \
  --property=User=omenka \
  --property=Group=omenka \
  --property=WorkingDirectory=/home/omenka/Projects/swarm-control-plane/worker \
  --property=NoNewPrivileges=yes \
  --property=ProtectSystem=strict \
  --property=ProtectHome=read-only \
  --property=PrivateTmp=yes \
  --property=PrivateDevices=yes \
  --property=ProtectKernelTunables=yes \
  --property=ProtectKernelModules=yes \
  --property=ProtectKernelLogs=yes \
  --property=ProtectControlGroups=yes \
  --property=RestrictRealtime=yes \
  --property=RestrictSUIDSGID=yes \
  --property=LockPersonality=yes \
  --property=CapabilityBoundingSet= \
  --property='RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK' \
  --property=ReadWritePaths=/var/lib/invariance-swarm/codex-discovery-runtime \
  --property=ReadWritePaths=/home/omenka/Projects/swarm-agent-workspaces \
  --property=ReadWritePaths=/home/omenka/.local/state/invariance-swarm \
  --setenv=PYTHONDONTWRITEBYTECODE=1 \
  --setenv=NODE_OPTIONS=--jitless \
  --setenv=SWARM_ENGINEERING_VIRTUALENV=/home/omenka/Projects/bulletproof_bt/.venv \
  --setenv=PATH=/home/omenka/Projects/swarm-control-plane/worker/.venv/bin:/usr/bin:/bin \
  --setenv=VIRTUAL_ENV=/home/omenka/Projects/swarm-control-plane/worker/.venv \
  /home/omenka/Projects/swarm-control-plane/worker/.venv/bin/python \
  /home/omenka/Projects/swarm-control-plane/worker/scripts/alpha_loop_rehearsal.py \
  --codex-home /var/lib/invariance-swarm/codex-discovery-runtime \
  --output /home/omenka/.local/state/invariance-swarm/alpha-loop-rehearsal/production-parity.json

jq -e '
  .success == true and
  .production_state_mutated == false and
  .capital_or_order_authority == false and
  .lease_routing.generic_coder_eligible == false and
  .lease_routing.dedicated_engineer_eligible == true and
  (.lifecycle.checks | all(.[]; . == true)) and
  .lifecycle.production_api_calls == 0 and
  .lifecycle.orders_submitted == 0 and
  .lifecycle.next_queue_depth == 1 and
  .terminal_receipt.declared_variant_count == 8 and
  .terminal_receipt.window_days == 365
' /home/omenka/.local/state/invariance-swarm/alpha-loop-rehearsal/production-parity.json \
  >/dev/null

install -o root -g root -m 0644 \
  "$source_dir/invariance-swarm-alpha-strategy-engineer.service" \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable invariance-swarm-alpha-strategy-engineer.service
systemctl restart invariance-swarm-alpha-strategy-engineer.service
systemctl is-active --quiet invariance-swarm-alpha-strategy-engineer.service
echo "Production-parity rehearsal passed; dedicated alpha strategy engineer installed."
