# RI-007 Validation Record

## Implemented

- Durable, digest-bound corpus synchronization runs and item history.
- Canonical founder-inbox ingestion with explicit quarantine/remediation outcomes.
- Rename, duplicate, replacement, and missing-source reconciliation without deletion.
- Complete coverage manifests and deterministic coverage digests.
- Retrieval projection rebuild after Mission Control refresh.
- Legacy Hermes inventory that fails closed when the primary artifact is unavailable.
- Canonical bounded Bulletproof projection registration without copying its raw lake.
- Protected operator script and recovery runbook.

## Acceptance boundary

Validated on 2026-08-10:

- Backend: 208 tests passed.
- Mission Control: 41 tests passed.
- Focused worker memory bridge, API client, and executor: 18 tests passed.
- Ruff passed for every changed backend, Mission Control, and worker surface.
- Alembic reported the single head `4d8f1b2c6a70`.
- A disposable PostgreSQL 17 database upgraded from an empty database through every
  revision, exposed both RI-007 tables and two append-only triggers, downgraded RI-007,
  and upgraded back to the same head.

Automated fixtures cover text/book classification, canonical direct upload, duplicate
refresh, rename, supersession, unsafe paths, malformed contracts, interrupted writes,
cross-project access denial, unpublished evidence, and bounded Bulletproof receipts.
The existing RI-002/003/005 suites cover mixed/corrupt PDF recovery, coordinate replay,
backup restore, queue recovery, and deterministic projection rebuild.

The full worker suite has two pre-existing VM2 PostgreSQL preflight fixture failures
concerning the client-TLS layout; 183 worker tests pass. RI-007 does not modify those
broker or deployment files. The focused changed worker surfaces pass all 18 tests.

Production VM2 migration and Mac refresh remain governed deployment actions. Their
receipts must be appended here before describing the live corpus as fully migrated.
