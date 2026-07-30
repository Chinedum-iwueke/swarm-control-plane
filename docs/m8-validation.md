# M8 Research Mission Validation

Date: 2026-07-30

## Scope

M8 implements the first bounded research-program path:

```text
research program
  -> predeclared hypothesis
  -> deterministic synthetic dataset
  -> isolated experiment
  -> out-of-sample metrics
  -> robustness and selection-bias audit
  -> digest-bound evidence and report
  -> accepted or rejected finding
```

## Security and research-integrity controls

- strict Pydantic contract with unknown fields forbidden;
- one allowlisted repository, workflow, dataset family, and hypothesis;
- bounded seed, observations, split, costs, and acceptance thresholds;
- no command field or task-supplied executable;
- no shell, Codex, external model, market-data network, or secret access;
- detached Git worktree and read-only primary checkout;
- deterministic standard-library generator and canonical JSON hashing;
- temporal train/out-of-sample split;
- doubled-cost and lag perturbation checks;
- one-hypothesis selection count;
- explicit synthetic-data and model-risk limitations;
- findings are always marked `production_eligible=false`;
- evidence, audit, report, logs, and completion payload are bounded.

## Automated evidence

- worker suite: 122 tests passed;
- worker Ruff and compileall passed;
- exact pilot dataset and out-of-sample metrics are regression-tested;
- repeated executions produce the same evidence digest;
- evidence-file digest equals the bounded result digest;
- unsafe repository, dataset, base ref, and command fields are rejected;
- root execution is rejected;
- accepted and rejected hypotheses are both valid terminal research outcomes;
- role-package workflow digest and permission profile are verified.

## Operational evidence

Pending reviewed Git promotion, dedicated agent/package deployment, and the
supervised one-shot pilot in `docs/runbooks/m8-research-mission.md`.

## Interpretation limit

An accepted M8 finding means only that the predeclared synthetic hypothesis met
the pilot thresholds and integrity audit. It is not evidence of live-market
edge and cannot authorize deployment, capital allocation, or trading.
