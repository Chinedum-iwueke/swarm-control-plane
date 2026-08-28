# RL-002 Conservative Off-Policy Proposal Evaluation

RL-002 evaluates a target-policy proposal only on a qualified RL-001 dataset, with a
current non-blocked DISC-007 selection audit and a qualified ML-004 calibration record.
It compares independently digest-bound estimators, lower confidence bounds, action
overlap and reward/support/cost stresses. It neither trains nor deploys a policy.

## Gate

The service derives the conservative value as the worst lower bound across estimators
and required stress scenarios. A proposal is rejected for a value below the declared
floor, estimator disagreement, weak effective sample size, unsafe importance weights,
weak overlap, excess extrapolation, unsupported actions, or any failed stress. The
target's base candidate must equal the ML-004 candidate and every estimator must have
been allowed by the bound RL-001 contract.

Passing yields only `shadow_eligible`. The record explicitly denies causal-policy,
deployment, order and capital authority.

## Deployment and replay

Apply migration `e8c3b6a05d40`, rebuild the API, and run:

```bash
python worker/scripts/rl002_pilot.py --output /var/lib/invariance-swarm/rl002/report.json
```

## Rollback

Stop new evaluations and treat affected proposals as rejected. Immutable comparisons
remain readable. RL-001 source contracts, DATA-002 builds, SHADOW-001 journals and
ML-004 assessments are not mutated.
