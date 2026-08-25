# GOV-004 immutable audit and policy evidence export

## Purpose

GOV-004 emits a portable, signed reconstruction of founder proposals, tasks, approval
events, operational-control events, operation-ledger events, GOV-001 authority policy
and decisions, and GOV-002/003 lifecycle events and consequences. It does not grant
authority or replace the canonical PostgreSQL histories.

## Contract

- Schema: `governance-audit-export-v1.0.0`.
- Records are normalized by source time, stream and immutable source identity.
- Every event binds actor, action, object identity/digest, policy identity/digest,
  evidence references, redacted payload and redaction receipts.
- Sequence numbers are contiguous and each event hashes its predecessor.
- The unsigned bundle digest is signed with Ed25519. The public key and its SHA-256 key
  identity travel with the export, so verification requires no database access.
- Persisted exports are append-only. A new export is a new record, never a mutation.
- Cross-stream references must resolve inside the bundle: proposals to source tasks,
  events to tasks/approvals/operations, lifecycle transitions to authority decisions,
  decisions to policies, and consequences to transitions and reversals.
- Keys containing password, secret, token, credential, private-key, API-key or
  signing-key markers are replaced with their value digest and explicit path receipt.

## API

- `POST /v1/governance-audit/exports` creates and retains a signed export.
- `GET /v1/governance-audit/exports/{id}` retrieves the exact retained bundle.
- `POST /v1/governance-audit/verify` verifies an arbitrary bundle and reconstructs
  lifecycle projections without privileged database interpretation.

All routes require the orchestrator credential. Verification rejects unsupported
versions, count drift, missing or reordered events, broken chains, altered content,
terminal-digest drift, key substitution and invalid signatures.

## Deployment and pilot

Deploy migration `c1f4a7d92e60`, rebuild the API, then run on VM1:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/gov004_pilot.py
'
```

The pilot creates a live export, verifies its signature and replay, retrieves the
persisted copy, and proves a modified actor fails with HTTP 422. Its report is mode
`0600` at `/var/lib/invariance-swarm/gov004/report.json`.

## Rollback

Restore the prior API image. Retain the additive table and every export because they
are audit evidence. A later compatible projector or verifier may replace the reader;
it must not rewrite existing bundles or their signatures.
