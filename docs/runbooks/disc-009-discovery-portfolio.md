# DISC-009 discovery portfolio and information-gain scheduler

## Purpose

DISC-009 turns canonical research uncertainty into a bounded, diversified research-attention agenda. It ranks inquiry candidates by expected information gain per attention unit while preventing one domain or semantic cluster from consuming the portfolio.

The scheduler allocates attention only. It cannot create tasks, start autonomous sessions, approve work, promote research, place orders, or allocate capital.

## Canonical inputs

- current, non-stale domain-curriculum evaluations;
- active discovery maps bound to a daily research program in the same project;
- completed bounded autonomous sessions with immutable closeout digests.

Source uncertainty is derived server-side from the canonical source. Callers may declare decision relevance, feasibility, and attention cost, but cannot supply or override uncertainty.

## Allocation contract

1. Freeze a timezone-aware source epoch and scoring policy.
2. Verify every source identity, digest, project, status, and epoch.
3. Compute semantic novelty against competing candidates and prior completed sessions.
4. Rank deterministic expected information gain per attention unit.
5. Seed distinct domains, then fill remaining capacity under domain, cluster, count, and attention caps.
6. Retain every selected and rejected candidate with its score, immutable digest, rank, and counterfactual reason.
7. Emit one digest-chained allocation event and expose read-only replay routes.

## Production pilot

After migration `c2e6f9a31b50` and API deployment, run on VM1:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/disc009_pilot.py \
  --output /var/lib/invariance-swarm/disc009/report.json
'
```

The pilot must select at least two domains, retain at least one counterfactual decision, replay the exact allocation digest, and report all action-authority flags as false.

## Rollback

Stop creating new portfolio versions and keep existing records readable. Downgrade only after exporting portfolio, candidate, and event rows. No research execution or production state depends on this scheduler, so rollback cannot cancel or mutate research tasks.
