# Independent Alpha Strategy Reviewers

The two signed packages reuse `alpha002_bootstrap.py`; they do not reuse the
AGT-006 pilot's synthetic review completion. Each package permits only one review
capability, risk-zero strategy-review tasks, and read-only Bulletproof access.
Profiles use separate agent, package and context identities. Shared provider/model
dimensions remain explicitly declared; this is not proof of independent reasoning.

After the reviewed source is merged and installed, provision from VM1 using the
protected operator environment. No existing executor credentials are rotated.

```bash
sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
commit="$(git rev-parse HEAD)"
for role in spec causality; do
  state="/etc/invariance-swarm/alpha-${role}-reviewer-state.json"
  worker/.venv/bin/python worker/scripts/alpha002_bootstrap.py \
    --package "vm1-alpha-${role}-reviewer" \
    --state "$state" \
    --environment "/etc/invariance-swarm/alpha-${role}-reviewer.env" \
    --source-commit "$commit"
  worker/.venv/bin/python worker/scripts/alpha_strategy_reviewer_profile.py \
    --state "$state" --role "$role" --provider openai --model-family codex
done
ROOT
```

Provider/model declarations must match the configured reviewer runtime. Profile
registration fails on different package, capability, context or inactive identity.
This command alone does not install/start supervised services, approve strategy
code, admit data, execute backtests or issue an independent-review receipt. Actual
closure requires authenticated leased tasks, immutable typed verdicts and receipt
replay through the deployed control plane. Service installation, producer-profile
provisioning and engineering-author provenance remain required follow-up work.

## Inventory Recovery Boundary

The current native inventory's 10,000-object shard size leaves interrupted runs
below that threshold with progress only, not reusable receipts. Do not describe
progress logs as checkpoints. Native recovery must durably retain completed object
metadata and bind it to source/configuration and unchanged file identity; changed
files require revalidation. A full-root receipt still requires complete traversal,
including additions and deletions. Routine discovery should consult the catalog;
selected-window admission remains distinct from inventory metadata.
