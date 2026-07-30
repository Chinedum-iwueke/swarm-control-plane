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

- worker suite: 123 tests passed;
- worker Ruff and compileall passed;
- exact pilot dataset and out-of-sample metrics are regression-tested;
- repeated executions produce the same evidence digest;
- evidence-file digest equals the bounded result digest;
- unsafe repository, dataset, base ref, and command fields are rejected;
- root execution is rejected;
- accepted and rejected hypotheses are both valid terminal research outcomes;
- role-package workflow digest and permission profile are verified.

## Operational evidence

- implementation PR: `#17`, merged as
  `8914a183a21588e74a928157a8e03da6a0f1a655`;
- execution-boundary correction PR: `#18`, merged as
  `510883dcd35bdc81ebfe9ed3c2559ab47f042109`;
- dedicated agent: `vm1-research-runner`
  (`23c62000-1fad-48bb-8ce5-3f4cb26f3779`);
- role package: `fecbfe26-9229-42a2-96b7-40efc6871a55`;
- failed-closed discovery task:
  `e455718a-5c61-4761-9984-6d7c6ca21ada`;
- successful pilot task:
  `4e2feecf-3dbc-4946-9bbf-1613ddf211ce`;
- successful task status: `succeeded`, attempt `1`, worker `0.3.2`;
- agent and machine: `vm1-research-runner` on `vm1-developer`;
- event sequence: created, leased, started, five heartbeats, completed;
- isolated source commit:
  `10b8870ad5e80b6dab6e7362ad1d4033302266db`;
- evidence SHA-256:
  `a68317817f2b39c760f1c4743050ad6a5d5719b51db543c5b0eb9983b4d398c8`;
- dataset SHA-256:
  `dbf9ec957b3987607b5abe9794a8f0ce33a0e06cc624ae10fcaec6b19446a46b`;
- result artifact: `research-evidence.json`, 1,917 bytes;
- audit artifact: `research-audit.json`, 818 bytes;
- report artifact: `research-report.md`, 876 bytes;
- all local artifacts and logs were mode `0600`;
- registered artifact hashes matched their local files;
- workspace metadata, detached worktree HEAD, and `bulletproof_bt/main`
  resolved to the same commit;
- the primary checkout retained the same pre-existing user changes observed
  before execution;
- workspace, task, result, failure, and event secret-pattern scans were clean.

The first task failed before subprocess execution because the shared validation
executor omitted the new task type from its ownership allowlist. It produced no
logs or stale completion, exhausted its single attempt, and remained preserved
for audit. PR `#18` added the missing boundary entry and a real-path regression
test before the successful task was created.

## Research result

- verdict: `accepted`;
- production eligible: `false`;
- audit passed: `true`;
- selected hypotheses: `1`;
- out-of-sample observations: `420`;
- out-of-sample trades: `121`;
- out-of-sample annualized Sharpe: `6.24037808`;
- out-of-sample maximum drawdown: `0.02786945`;
- doubled-cost annualized Sharpe: `5.6414941`;
- lag-stress annualized Sharpe: `1.77915523`.

These values are deterministic synthetic pilot evidence. They are intentionally
unsuitable for claims about live performance.

## Recommendation

**Go** for the completed M8 bounded research-execution capability and further
supervised synthetic research tasks. **No-go** for live-market inference,
capital allocation, strategy deployment, parameter search, private/live data,
or enabling a continuous research daemon. Each expansion requires a separately
reviewed contract, workflow, data policy, and operational pilot.

## Interpretation limit

An accepted M8 finding means only that the predeclared synthetic hypothesis met
the pilot thresholds and integrity audit. It is not evidence of live-market
edge and cannot authorize deployment, capital allocation, or trading.
