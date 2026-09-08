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
additionally requires migration `d2e8f5b13a70`, a replayable RI-009B curriculum
baseline, the enabled VM2 orchestrator, one live delta reconciliation, one
no-change cycle and one successful `ri016_pilot parity` receipt. Until those live
receipts exist, source is complete but production freshness is not yet claimed.
