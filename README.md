# Swarm Control Plane

Central task orchestration and monitoring system for the agent network running
across the founder MacBook, the development VM, and the deployment VM.

## Design

The system architecture, trust boundaries, lifecycle contracts, current
implementation status, and open design decisions are documented in
[`docs/hermes-swarm-system-design.md`](docs/hermes-swarm-system-design.md).
The dependency-ordered implementation roadmap and early agent catalog are in
[`docs/hermes-swarm-delivery-plan.md`](docs/hermes-swarm-delivery-plan.md).
The Mac-local founder interface and private cited-search pilot are documented
in [`mission-control/`](mission-control/README.md).

## Intended components

- FastAPI orchestrator API
- PostgreSQL task and audit database
- Redis queue and event transport
- Agent registration and heartbeats
- Task assignment, claiming, leases, and retries
- Approval workflows
- Artifact tracking
- Telegram founder interface
- Web dashboard
- Shared task and evidence schemas

## Machines

- mac-founder
- vm1-developer
- vm2-deployment

## Machine-verifiable implementation baseline

The repository ships a read-only `implementation-baseline-v1` collector. It
records the Git pin and dirty state, sanitized origin, runtime versions,
dependency and lock-file state, tracked schema hashes, declared acceptance
commands, and the controlled claim vocabulary. It does not read environment
values, ignored files, raw datasets, or credentials.

```bash
python worker/scripts/implementation_baseline.py collect \
  --repository . \
  --output /tmp/swarm-control-plane-baseline.json
python worker/scripts/implementation_baseline.py validate \
  /tmp/swarm-control-plane-baseline.json
```

Collection fails closed on a dirty worktree. `--allow-dirty` is available for
audits and records the affected tracked/untracked paths in the evidence rather
than claiming a release-quality baseline. CI publishes the validated JSON as a
30-day workflow artifact. The canonical schema is
[`schemas/implementation-baseline-v1.schema.json`](schemas/implementation-baseline-v1.schema.json).
