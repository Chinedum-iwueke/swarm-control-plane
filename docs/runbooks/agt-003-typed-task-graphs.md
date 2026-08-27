# AGT-003 Typed Task Graphs and Bounded Deliberation

## Purpose

AGT-003 turns a multi-agent plan into a fixed, digest-bound DAG whose work is still executed through normal Hermes tasks, approvals, capability grants, context manifests and leases. It does not grant execution or capital authority.

## Contract

- Every graph declares an immutable node ceiling, total-attempt budget, duration, parallelism and deadline.
- Every node declares a role, typed input and output, task contract, stop conditions, dependencies and optional compensation task.
- Cycles, unknown dependencies, duplicate keys and over-budget manifests are rejected before persistence.
- Activation materializes ordinary governed tasks and `task_dependencies`; graph mutation is then closed.
- The lease selector enforces dependencies, graph parallelism, agent capability, machine, authority and approval together.
- Heartbeats return cancellation state. Restricted workers stop cooperatively and release the lease; queued nodes cancel immediately.
- A task failure fails the graph closed, cancels unfinished descendants and materializes declared compensation in reverse graph order.
- The Mission Supervisor reconciles active graphs continuously, including deadlines, exhausted attempts, cancellation, compensation and deadlock.
- Typed messages and graph events carry SHA-256 digests. Events form a previous-digest chain for replay.

## Recovery

Do not edit an active manifest or task row. Cancel the graph through `POST /v1/task-graphs/{id}/cancel`, allow workers to acknowledge cancellation through lease release, execute declared compensation tasks, and retain the terminal event chain. A replacement plan is a new graph key and digest.

## Validation

Run backend and worker suites, migrate a disposable PostgreSQL database to `b3e7a1c52d90`, then run:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/agt003_pilot.py \
  --output /var/lib/invariance-swarm/agt003/report.json
'
```

The pilot is deliberately cancelled before lease. It proves graph creation, activation, dependency materialization, typed message retention, bounded cancellation and digest-chain replay without executing a workload.
