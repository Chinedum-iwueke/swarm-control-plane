# DISC-001 Daily Research Director Runbook

## Deploy

Deploy the control-plane API, apply Alembic migration `a8c4e1d72b90`, and reinstall
Mission Control from the same source commit. Confirm `/health` and `alembic current`
before reconciling a program.

## Reconcile and inspect

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/disc001_pilot.py \
  --output /var/lib/invariance-swarm/disc001/report.json
'
```

Review the question, source mode, publication/citation lineage, score components and
question digest in Mission Control. Reject stale, poorly grounded or operationally
mis-scoped questions.

## Approve the bounded pilot

Use Mission Control's Approve action, or rerun the command with `--approve` after the
review. Approval emits `approved` and `task_ready`; it does not create or run a trial.

## Failure handling

- No current qualified candidate: accept the deterministic static fallback or wait for
  new approved surveillance evidence.
- Digest conflict: refresh Mission Control and review the new proposal.
- Weekly budget exhausted: do not bypass it; wait for the next budget window.
- Stale projection or evidence: repair Research Intelligence freshness before retrying.
