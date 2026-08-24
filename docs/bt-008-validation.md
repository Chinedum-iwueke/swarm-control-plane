# BT-008 Validation

BT-008 closes the laboratory publication boundary without duplicating the
existing research registry.

Implemented evidence:

- digest-verified join across registered experiment, trial, result, reviews,
  decision, and Bulletproof canonical run;
- atomic canonical result/review/decision/dossier publication;
- durable ordered publication events and replay API;
- fail-closed projection receipts tied to current graph and retrieval epochs;
- fail-closed, idempotent Bulletproof memory receipt;
- retained negative and invalid outcomes;
- resumable projection and memory failures with no canonical deletion.

Focused validation covers request and lineage mismatch, missing reviews,
negative-result retention, stage ordering, immutable receipts, partial failure,
local memory idempotency, identity collision, bundle integrity, and full
run-to-memory resume behavior.
