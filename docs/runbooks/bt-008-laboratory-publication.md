# BT-008 Laboratory Publication Runbook

## Boundary

BT-008 publishes one already registered and reviewed research trial. The
finalized Bulletproof bundle is immutable source evidence; Hermes is the
canonical registry; graph, retrieval, and Bulletproof research memory are
derived consumers.

## State machine

1. `POST /v1/research/laboratory/publications` validates every supplied digest
   against the registered trial and canonical run. It atomically creates the
   result, two review objects, decision, replay dossier, publication, and first
   event.
2. The publication waits in `awaiting_projections`. Rebuild graph and retrieval
   projections against the new corpus epoch.
3. Submit their exact receipts to `/{id}/projections`. Hermes rejects stale or
   invented receipts and advances to `awaiting_memory`.
4. Bulletproof writes its idempotent local memory consumer row and submits the
   digest-bound receipt to `/{id}/memory`.
5. Hermes advances to `complete`. `/{id}/replay` returns the immutable event
   transcript and all consumer receipts.

Failures are recorded through `/{id}/failures` as `projection_failed` or
`memory_failed`. Retrying the same request digest resumes the existing record.
Canonical evidence is never compensated by deletion. Disable new callers to
roll back intake; retain bundles and canonical records, then rebuild or restore
derived projections independently.

## Operator checks

- Run Alembic through `d4a7c9e21b60`.
- Confirm the six laboratory routes in OpenAPI.
- Confirm the run object includes market-model, representation, and search-plan
  digests before publishing.
- Exercise a negative result and verify it reaches `complete` and remains
  citation-replayable.
- Repeat the exact request and confirm the same publication and memory row are
  returned.
