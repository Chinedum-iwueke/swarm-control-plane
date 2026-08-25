# OPS-003 disaster recovery and runtime replacement

## Authority boundary

OPS-003 proves recovery in disposable or parity environments. It does not authorize a
production restore, delete a canonical store, rotate an undisclosed credential, or
change the active model/runtime. Those mutations require their own approved,
digest-bound plans.

## Integrated rehearsal contract

One dossier binds:

1. an integrity-verified OPS-005 control-plane backup and network-isolated restore;
2. an RI-005 canonical corpus backup/restore, fresh retrieval and graph projections,
   and citation replay;
3. stale-lease reclamation, exactly-once task replay and one deduplicated founder
   notification;
4. a schema-compatible replacement runtime that reproduces the canonical task output
   and can fall back to the prior runtime; and
5. redacted credential-rotation evidence proving new activation and old revocation.

Every section receives a SHA-256 digest and the dossier itself is content addressed.
Credential-shaped fields fail validation. RPO and RTO measurements must remain within
the declared policy.

## Local deterministic rehearsal

Run worker/scripts/ops003_rehearsal.py with PYTHONPATH set to worker/src and provide an
output path outside the repository. The fixture exercises composition and fail-closed
behavior without touching production.

Intended-machine acceptance replaces each fixture section with evidence from the
existing OPS-005 and RI-005 drills, an isolated stale-lease/task replay, a redacted
credential rotation, and an approved runtime replacement/fallback rehearsal.

## Rollback

- Never restore over the production database during rehearsal.
- Keep the prior verified backup generation and runtime package.
- On replacement mismatch, deactivate the replacement and replay through the prior
  runtime.
- On projection mismatch, retain canonical restored objects and rebuild derived state.
- On task replay uncertainty, freeze new leases until reconciliation proves exactly
  one terminal execution.
