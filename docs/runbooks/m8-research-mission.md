# M8 Reproducible Research Pilot

## Objective

Run one predeclared synthetic-market hypothesis from a strict research program
through isolated execution, robustness and selection-bias audit, artifact
registration, and an accepted/rejected report.

This pilot validates the research platform. It does not validate a live trading
strategy.

## Boundaries

- dedicated agent: `vm1-research-runner`;
- task type: `research_experiment`;
- workflow: `research-experiment`;
- repository: `bulletproof_bt`;
- machine: `vm1-developer`;
- risk ceiling: 1;
- detached Git worktree at an explicit committed base ref;
- synthetic dataset only;
- one fixed hypothesis and no parameter search;
- no shell, Codex, network data, primary-checkout writes, Git remote writes, or
  production promotion.

The existing dirty `bulletproof_bt` primary checkout is not modified. The
workspace resolves committed `main` independently.

## Source validation

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
. .venv/bin/activate
python -m compileall -q src
pytest -q
ruff check src tests scripts
```

## Agent bootstrap

With the protected operator environment, create the dedicated identity and
write its credential directly to a protected staging file:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/bootstrap_research_agent.py \
  --token-output /home/omenka/.vm1-research-token.staged
'
```

Install a root-owned mode-`0600` research environment derived from the existing
VM1 worker environment. Change only:

- `SWARM_AGENT_TOKEN`;
- `SWARM_AGENT_SLUG=vm1-research-runner`;
- `SWARM_ROLE_PACKAGE_MANIFEST` to the research manifest.

Do not print either credential.

## Package registration

Register `role-packages/vm1-research-runner/manifest.yaml` with the merged
source commit, then bind it to the dedicated agent using
`scripts/package_registry.py`.

## Pilot task

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/research_tasks.py create \
  --program research-programs/m8-pilot.yaml
'
```

Run exactly one research cycle with the dedicated environment. Do not enable a
continuous research service in M8.

## Required evidence

- task succeeds on attempt 1 under `vm1-research-runner`;
- source commit equals committed `bulletproof_bt/main`;
- primary checkout status is unchanged;
- dataset digest is reproducible from seed and program;
- train and out-of-sample metrics are distinct;
- doubled-cost and lag perturbations are recorded;
- audit records one selected hypothesis and passes every integrity check;
- evidence digest matches the registered result artifact;
- audit and report artifacts are registered;
- report states `Production eligible: no`;
- completion result is bounded and excludes raw observations;
- event order is created, leased, started, heartbeats, completed;
- no token appears in logs, artifacts, task events, or result.

## Stop conditions

Stop on contract ambiguity, changed primary-checkout state, live/private data
access, more than one hypothesis, parameter search, audit failure, lease loss,
artifact digest mismatch, or any production/live-trading request.
