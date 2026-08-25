# GOV-001 authority policy operations

## Boundary

The authority graph answers whether a named principal may perform a specific action
on a digest-bound object in a declared scope and risk tier. It does not grant operating
system permissions, reveal secrets, or replace the task broker.

## Deploy

1. Deploy the API migration `e6b1a4d82f90` and rebuild the API.
2. From VM1, source `pilot-operator.env` and run
   `worker/scripts/gov001_bootstrap.py`.
3. Reinstall Mission Control on the Mac.
4. Confirm `/v1/authority/overview` reports policy version `1.0.0` as active.
5. Replay one low-risk independent approval and one high-risk self-approval denial.

The bootstrap is idempotent. Re-running it returns the already active policy.

## Delegation and exceptions

Delegations are explicit grants, never role mutations. They expire within 30 days and
cannot exceed the grantor's risk or decision boundary. Multiple applicable grants are
an ambiguity and therefore deny the action.

Exceptions expire within 24 hours, retain their reason and compensating controls, and
require a governance approver distinct from both requester and reviewer. Constitutional
boundaries are not waivable.

## Rollback

A retired policy snapshot may be reactivated through the policy activation endpoint.
When an active policy exists, that rollback requires an authorized, digest-bound
`policy-activation` decision under the current policy. Database rollback is reserved
for reverting the entire feature before any authority records are relied upon.
