# RI-016 Validation

Source acceptance requires:

- a durable, transaction-linked object/edge/alias change ledger;
- deterministic incremental/full strategy selection with a bounded delta;
- coalescing under a PostgreSQL advisory lock;
- independently resumable retrieval, graph, curriculum and verification phase
  receipts;
- provenance-aware invalidation and terminal corpus/projection epoch checks;
- exact curriculum case retention and an honest `awaiting_rebaseline` state for
  legacy evaluations;
- operation-ledger and Mission Control visibility;
- zero-work behavior for an already-current corpus;
- a full-rebuild fallback and a live incremental/full content-digest parity
  pilot.

Automated source validation covers strategy boundaries, deterministic versioning,
route/migration contracts, retained curriculum cases, existing retrieval/graph
behavior, Mission Control API behavior and JavaScript syntax. Production closure
additionally requires migration `d2e8f5b13a70`, an enabled VM2 orchestrator
projection pass, a replayable RI-009B curriculum baseline, one live delta reconciliation, one
no-change cycle and one successful `ri016_pilot parity` receipt. Until those live
receipts exist, source is complete but production freshness is not yet claimed.

## Production evidence

Production closure passed on 2026-09-09 at corpus epoch `577353`. RI-009B
portfolio `1.2.0` qualified all thirteen Research Bible domains under unchanged
strict thresholds; portfolio `d2c7e23e-d592-47e8-9440-2cd325ba146c` has record
digest `1661103ddcf5d9814f54d21cb08b1f04b2b8e44bbe4377f9eabf4ec0bd99f9b7`.
The derived-state status then reported zero pending changes and `current=true`.

Forced-full parity run `43885a98-501b-436a-9162-6f8fe4c9cdd5` completed with
`outcome=succeeded` and `incremental_full_digest_parity=true`. Retrieval digest
`1ba49d4e2368a78fdace74ca5d865b58ba92e6f249a3202275f119c6e06e26ea`
and graph digest
`c0eaf61a7a01d5058637206abf2bef575f784efb33d9c296ef9a298eb0ea1988`
were identical before and after the clean full rebuild. The terminal report also
recorded zero pending changes and `current=true`; RI-016 is production-complete.
