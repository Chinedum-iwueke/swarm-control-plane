#!/usr/bin/env bash
set -euo pipefail

((EUID == 0)) || { printf 'Run this installer as root.\n' >&2; exit 1; }
root=/home/omenka/Projects/swarm-control-plane
native=/home/omenka/Projects/bulletproof_bt
environment=/etc/invariance-swarm/alpha-method-designer.env
state=/etc/invariance-swarm/alpha-method-designer-state.json
unit=invariance-swarm-alpha-method-designer.service

# Installation is deliberately separate from authorization and activation.
if systemctl is-active --quiet "$unit"; then
  printf 'Drain and stop the method designer before replacing its runtime.\n' >&2
  exit 1
fi
for file in "$environment" "$state" /etc/invariance-swarm/codex-discovery-runtime.env; do
  test ! -L "$file"
  test "$(stat -c '%u:%a' "$file")" = 0:600 || {
    printf 'Require root-owned mode 600: %s\n' "$file" >&2; exit 1;
  }
done
test -x "$root/worker/.venv/bin/invariance-swarm-worker"
test -x "$native/.venv/bin/python"
test -d "$native/.git/worktrees"
test -d /var/lib/invariance-swarm/codex-discovery-runtime
"$root/worker/.venv/bin/python" - "$environment" "$state" /etc/invariance-swarm/codex-discovery-runtime.env <<'PY'
import json
from pathlib import Path
import sys
lines = Path(sys.argv[1]).read_text().splitlines()
pairs = [line.split('=', 1) for line in lines if line and not line.startswith('#')]
if any(len(pair) != 2 for pair in pairs) or len({p[0] for p in pairs}) != len(pairs):
    raise SystemExit('Malformed or duplicated runtime settings')
env = dict(pairs)
state = json.loads(Path(sys.argv[2]).read_text())
if (state.get('slug') != 'alpha-method-designer'
        or env.get('SWARM_AGENT_SLUG') != state['slug']
        or not state.get('method_model')
        or env.get('SWARM_CODEX_MODEL') != state['method_model']
        or env.get('SWARM_ENGINEERING_AUTHOR_PROVIDER') != 'codex'):
    raise SystemExit('Method runtime provenance differs from registration')
runtime_lines = [line for line in Path(sys.argv[3]).read_text().splitlines()
                 if line and not line.startswith('#')]
if runtime_lines != ['SWARM_CODEX_HOME=/var/lib/invariance-swarm/codex-discovery-runtime']:
    raise SystemExit('Shared runtime file must not override method model or provider settings')
PY
install -d -o omenka -g omenka -m 0700 /home/omenka/Projects/swarm-agent-workspaces
install -o root -g root -m 0644 "$root/worker/systemd/$unit" "/etc/systemd/system/$unit"
systemd-analyze verify "/etc/systemd/system/$unit"
systemctl daemon-reload
printf 'Method designer installed, not started or enabled. Exact commissioning approval is still required.\n'
