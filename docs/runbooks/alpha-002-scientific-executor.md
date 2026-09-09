# ALPHA-002 Continuous Scientific Executor Runbook

## Purpose and authority boundary

ALPHA-002 turns an activated ALPHA-001 campaign into continuously leased native
Bulletproof work. Hermes selects and leases one immutable discovery question at a
time. The VM1 executor checks out the frozen Bulletproof commit, reads the admitted
panel, and either executes an exact registered hypothesis or retains a strategy
engineering requirement with zero trials. Similarity is never used to substitute a
strategy.

The package has no capital, order, production-promotion or self-approval authority.
A successful scientific result can become only a prospective shadow candidate. Demo
and live activation remain behind their separate execution, risk and founder gates.

## Deploy the control plane on VM2

ALPHA-002 reuses the ALPHA-001 schema, so no new migration is introduced.

```bash
sudo bash <<'ROOT'
set -euo pipefail
repo=/srv/invariance/swarm/repositories/swarm-control-plane
runtime=/srv/invariance/swarm/control-plane-runtime

git -C "$repo" pull --ff-only origin main
cd "$runtime"
docker compose build api
docker compose up -d --no-deps --force-recreate api

for attempt in $(seq 1 60); do
  status="$(docker inspect swarm-api --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}')"
  [[ "$status" == healthy ]] && break
  sleep 2
done
test "$(docker inspect swarm-api --format '{{.State.Health.Status}}')" = healthy
ROOT
```

## Bootstrap and install the VM1 executor

Use full merged commit identities for both repositories. The bootstrap is idempotent
for the same package and commit and refuses implicit credential rotation or partial
state repair.

```bash
cd /home/omenka/Projects/swarm-control-plane/worker

sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

.venv/bin/python scripts/alpha002_bootstrap.py \
  --state /etc/invariance-swarm/alpha002-executor-state.json \
  --environment /etc/invariance-swarm/alpha002-executor.env \
  --source-commit "$(git -C /home/omenka/Projects/swarm-control-plane rev-parse HEAD)"

./systemd/install-alpha-research-executor.sh --enable --start
ROOT
```

The campaign must bind the current full Bulletproof commit. Regenerate and register
the ALPHA-001 data-admission receipt after the Bulletproof merge before activating a
new campaign; an older campaign remains immutable and does not silently change code.

Create a new campaign version explicitly opted into ALPHA-002 after the matching
admission receipt exists:

```bash
sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker

.venv/bin/python scripts/alpha001_bootstrap.py \
  --receipt /home/omenka/.local/state/alpha001/bybit-btcusdt-1m-admission.json \
  --state /etc/invariance-swarm/alpha002-campaign-state.json \
  --campaign-key ALPHA002-REAL-DATA \
  --version 1.0.0 \
  --portfolio-id <exact-disc-009-portfolio-uuid> \
  --execution-protocol alpha002-native-v1 \
  --activate
ROOT
```

## Observe execution

Mission Control exposes the current task number, lease state, attempt count,
heartbeat, disposition and failure. Telegram emits queued and terminal campaign
updates. The service log is the local operational view:

```bash
systemctl is-enabled invariance-swarm-alpha-research-executor.service
systemctl is-active invariance-swarm-alpha-research-executor.service
sudo journalctl \
  -u invariance-swarm-alpha-research-executor.service \
  -f --no-pager --output=cat
```

Native bundles are retained under
`~/.local/share/invariance-swarm/alpha002-bundles/<bundle-digest>` and the native
publication precommit is stored in
`~/.local/state/invariance-swarm/alpha002-memory.sqlite`. Both paths are writable only
by the unprivileged executor account. The admitted market-data tree and primary
Bulletproof checkout are read-only to the service.

## Failure, retry and recovery

The generic Hermes task lease is the crash-recovery contract. Heartbeats extend the
lease while the native process runs. A native process failure is retried at most
three times; exhausted work moves the campaign to `needs_attention`. The fixed
workflow times out after six hours. A repeated bundle digest resumes against the
durable manifest and cannot overwrite different content.

Campaign cancellation marks queued work cancelled immediately and requests
cooperative cancellation from leased/running work. Unsupported questions finish as
`strategy_generation` failures with a cited engineering artifact and zero trials.
They are not operational crashes and must not be “fixed” by choosing a nearby
hypothesis.

## Candidate interpretation

The initial executor prospectively selects one registered variant and uses a temporal
60/20/20 representation contract. Candidate eligibility requires native truth,
point-in-time validation, reproducibility, at least 50 held-out trades, positive
held-out mean net R, positive mean net R after doubling observed cost drag,
selection-accounting evidence, distinct statistical/adversarial result reviews, a
complete BT-009 bridge, current retrieval/graph receipts and Bulletproof memory
confirmation. Failure of any criterion retains a negative result.

The review identities are separated in the research registry but are deterministic
policy evaluators executed by the publication coordinator. They are not claimed to
be provider- or context-independent AGT-006 agents. Any later promotion boundary must
require a genuine AGT-006 independence receipt.

## Rollback

```bash
sudo systemctl disable --now invariance-swarm-alpha-research-executor.service
```

Rollback stops new leases. It does not delete tasks, attempts, bundles, negative
results, bridge receipts or native memory. Cancel any still-running campaign through
its digest-bound API action.
