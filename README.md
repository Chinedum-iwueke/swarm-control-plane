# Swarm Control Plane

Central task orchestration and monitoring system for the agent network running
across the founder MacBook, the development VM, and the deployment VM.

## Design

The system architecture, trust boundaries, lifecycle contracts, current
implementation status, and open design decisions are documented in
[`docs/hermes-swarm-system-design.md`](docs/hermes-swarm-system-design.md).
The dependency-ordered implementation roadmap and early agent catalog are in
[`docs/hermes-swarm-delivery-plan.md`](docs/hermes-swarm-delivery-plan.md).

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
