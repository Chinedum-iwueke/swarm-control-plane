# PLAT-002 Workload Identity, Authorization and Secrets Lifecycle

## Purpose

PLAT-002 binds every runtime credential to the exact AGT-001 agent charter and role-package deployment that authorizes it. It adds explicit API scopes, bounded credential rotation, logical secret policies, redacted authorization receipts and reduction-only emergency access without creating a parallel authority system.

## Invariants

- The raw credential is returned once and only its HMAC digest and prefix are retained.
- Identity manifests bind agent, machine, audience, charter digest, package digest, scopes, owner and expiry.
- Wildcard scopes are invalid. Scope checks are centralized at the authenticated agent boundary.
- Enforcement activates only after every credential attached to an active package deployment is identity-bound.
- Secret policies retain logical references and lifecycle metadata, never secret values.
- Context keys that may contain secrets, tokens or passwords are omitted from authorization receipts.
- Emergency grants require founder approval and an independent reviewer, expire within one hour and can only halt, isolate or revoke.
- Package or charter revocation invalidates the workload identity immediately.

## Deployment

1. Deploy migration `f3a7c1d92e60` before recreating the API image.
2. Run `worker/scripts/plat002_bootstrap.py` with the root-owned pilot-operator environment.
3. Confirm `/v1/workload-identities/overview` reports enforcement active and no deployed credential uncovered.
4. Run `worker/scripts/plat002_pilot.py` and retain `/var/lib/invariance-swarm/plat002/report.json` mode `0600`.
5. Reinstall Mission Control so each agent card exposes its active workload identity and scope count.

## Rotation And Rollback

Rotation creates a 30-900 second overlap and a new credential bound to the same identity. Finalization revokes the prior credential. Rollback revokes the new credential and restores the prior scoped credential. Neither path broadens scopes or changes the identity manifest.

## Recovery

If bootstrap stops before activation, enforcement remains off and existing credentials continue operating. After activation, revoke a compromised identity or credential through the lifecycle API. A policy rollback must preserve identity binding and may not restore unscoped legacy credentials.
