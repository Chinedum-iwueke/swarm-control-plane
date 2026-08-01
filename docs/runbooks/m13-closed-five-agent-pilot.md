# M13 Closed Five-Agent Pilot Runbook

## Purpose

M13 validates one real-data, non-live signal experiment through five separately
authenticated and packaged roles. It does not construct a trading strategy, access an
exchange, optimize parameters, promote a signal, or authorize capital.

## Roles

1. `m13-senior-research-specialist` may retrieve evaluated knowledge, create a cited
   brief, and register one hypothesis. It cannot specify, execute, or review results.
2. `m13-experiment-specification` may create a manifest only after the hypothesis is
   approved. It has no result endpoint.
3. `m13-research-execution` may lease the approved task, execute the immutable manifest,
   and register its result. It cannot review or decide the result.
4. `m13-statistical-reviewer` may submit only an independent statistical review.
5. `m13-adversarial-auditor` may submit only an adversarial review.

Agent API identity is derived from the bearer token. Claimed actor names are not accepted
on these endpoints. Each endpoint also requires the matching active role-package
deployment and capability. A founder decision requires both review kinds from different
agents.

## Data boundary

The pilot snapshot is `worker/research-data/m13/binance-btcusdt-1h-2025.csv`.
It contains 8,760 UTC hourly BTCUSDT OHLCV rows derived without a network fetch from the
existing VM1 canonical Binance one-minute store. `manifest.json` binds the original
Parquet digest, aggregation, date range, row count, and CSV digest.

Task execution reads only this server-local allowlisted file and verifies its SHA-256.
The mutable canonical store is not mounted or read during execution. The specification
role never receives result data before the manifest is locked.

## Deployment

Deploy migration `e5f7a9b1c330` and rebuild the API on VM2 before bootstrapping roles.

## Bootstrap

Run as root on VM1 with the operator environment. The state file contains five agent
tokens and must remain root-only:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m13_bootstrap.py \
  --state /etc/invariance-swarm/m13-role-state.json \
  --source-commit SOURCE_COMMIT
'
```

## Prepare and approve

`prepare` creates the brief, hypothesis, snapshot, manifest, reserved trial, task, and
one pending founder approval. It does not approve or execute the task.

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m13_closed_loop.py prepare \
  --roles /etc/invariance-swarm/m13-role-state.json \
  --state /etc/invariance-swarm/m13-pilot-state.json \
  --repository-commit 10b8870ad5e80b6dab6e7362ad1d4033302266db
'
```

Approve exactly the returned approval ID and plan digest in Mission Control or Telegram.
The `execute` command waits up to two minutes for that specific task to become queued;
an early invocation cannot silently exit as successful `no_work`.

## Execute and finalize

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m13_closed_loop.py execute \
  --roles /etc/invariance-swarm/m13-role-state.json \
  --state /etc/invariance-swarm/m13-pilot-state.json
'

sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m13_closed_loop.py finalize \
  --roles /etc/invariance-swarm/m13-role-state.json \
  --state /etc/invariance-swarm/m13-pilot-state.json
'
```

Finalize independently reproduces the locked calculation, registers the execution result
under the execution token, submits reviews under the two reviewer tokens, records the
founder decision, and verifies lineage and searchability.

## Stop conditions

- Any digest, role package, identity, snapshot, or result mismatch.
- More than one task attempt or workspace.
- Missing founder approval.
- Same actor for statistical and adversarial review.
- Any live-trading, deployment, remote-write, or primary-checkout operation.
