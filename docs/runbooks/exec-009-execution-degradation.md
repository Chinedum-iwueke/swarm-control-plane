# EXEC-009 execution-degradation feedback runbook

EXEC-009 compares point-in-time venue and strategy observations with an immutable
threshold contract. Bulletproof owns measurement, diagnosis and incident production.
Hermes stores the active specification and exact producer receipt. Neither component
changes a strategy, restores eligibility, allocates capital or submits orders.

## Decision behavior

- One noncritical breach remains monitoring evidence and requests recalibration.
- Consecutive strategy-cost breaches request shadow fallback review.
- Consecutive venue or infrastructure breaches request route-restriction review.
- Missing or stale observations fail closed; service loss or stale venue rules request
  freeze/kill review immediately.
- Healthy observations after restriction, fallback, demotion or kill request an
  independent restoration review. They never reactivate execution automatically.
- Venue, model, strategy and infrastructure diagnoses remain separate and may coexist.

## Deterministic and cross-repository replay

Generate the native report in the Bulletproof checkout:

```bash
PYTHONPATH=src .venv/bin/python scripts/exec009_pilot.py \
  --output /var/lib/invariance-swarm/exec009/native-report.json
```

After migration `d7a3f1c59e20` and API deployment, register and replay it on VM1:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/exec009_pilot.py \
  --native-report /var/lib/invariance-swarm/exec009/native-report.json \
  --output /var/lib/invariance-swarm/exec009/report.json
'
```

## Rollback

Stop publishing new EXEC-009 receipts and retain the last immutable incident chain.
Keep the affected route restricted, candidate in shadow fallback, or runtime killed.
Restoration requires an independent accountable decision under the prior active
contract; rollback never treats missing evidence as recovery.
