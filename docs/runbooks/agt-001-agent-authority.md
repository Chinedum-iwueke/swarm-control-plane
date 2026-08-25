# AGT-001 agent authority registry

AGT-001 adds an immutable charter and bounded capability-grant layer to the existing
agent registration and signed role-package deployment records. It does not replace
those records. Effective authority is their intersection.

## Resolution contract

Before a governed lease is admitted, resolve its agent, machine, capability, task
type, repository and risk through `POST /v1/agent-governance/agents/{id}/resolve`.
An allow decision requires an enabled registration, one active charter, one active
package deployment and one unexpired grant to agree. The response binds the charter,
package and grant digests plus the accountable owner into a snapshot digest.

Charters are immutable. Activating a replacement supersedes the prior charter and
revokes its grants. Grant and revocation events form a digest chain. Revocation,
expiry, a stale package, a declared conflict or any scope mismatch fails closed.

No charter or grant implies capital allocation, order placement or live-trading
authority. Those remain separately constitutional and human governed.

Run `worker/scripts/agt001_bootstrap.py` after the migration and before resuming
workers. It derives one charter per active signed package and one independently
revocable grant per required capability. It is idempotent and never grants beyond
the registration or package.

## Rollback

Revoke the affected grant or active role-package deployment. Both immediately make
subsequent authority resolutions deny while retaining the prior records and event
chain for audit replay.
