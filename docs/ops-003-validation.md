# OPS-003 validation record

**Date:** 2026-08-25  
**Status:** Source-complete and deterministically rehearsed; production resources untouched

## Implemented

- Strict integrated recovery dossier with section and whole-document SHA-256 digests.
- Measured control-plane and corpus RPO/RTO policy gates.
- Backup identity, byte-size, integrity, migration and isolated-restore consistency.
- Corpus restore identity, retrieval/graph rebuild lineage and citation replay.
- Stale-lease reclamation, duplicate-execution rejection and notification deduplication.
- Schema-compatible runtime replacement, canonical-output parity and fallback proof.
- Secret-rotation activation/revocation/redaction checks.
- Explicit denial of production-restore authority.

## Reuse

The implementation composes OPS-005 control-plane backups, RI-005 corpus recovery,
existing projection rebuilds, worker lease semantics and notification behavior. It does
not introduce a second backup store, task registry, projection engine or model gateway.

## Acceptance boundary

The retained local rehearsal is deterministic and non-destructive. It proves the
cross-service evidence contract and adversarial failure handling. A future approved
intended-machine drill may substitute genuine current evidence without changing the
schema. Production restore remains a separately governed operation.

The worker suite passed 229 tests. The focused OPS-003 suite contributed 12 passing
cases. The deterministic rehearsal dossier digest is
`941a484ee954fe25a8c63bd256e7bd48699ca6cbba1c3486f5d7df8f081f7f71`;
its serialized file is mode `0600`, records zero production resources touched and
grants no production-restore authority.
