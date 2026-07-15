# Swarm Control Plane

Central task orchestration and monitoring system for the agent network running
across the founder MacBook, the development VM, and the deployment VM.

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
