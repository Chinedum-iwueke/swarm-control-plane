# RI-010 Memory Lifecycle Validation

RI-010 adds governed lifecycle semantics to canonical institutional memory. It
does not delete history silently and it does not give a model retention
authority.

## Contract

- Every canonical evidence object has one materialized lifecycle state.
- Active evidence can be consolidated, superseded, corrected, retracted,
  expired through explicit decay, or restored from a reversible state.
- Consolidation requires equal content digests and emits an immutable receipt.
- Registering a declared canonical successor automatically marks the prior
  object superseded in the same transaction.
- Retention holds name their authority and reason and block deletion.
- Lawful deletion requires a request with legal basis and a different approving
  authority. It removes the protected JSON payload while preserving a
  non-sensitive tombstone, original payload digest, canonical content digest,
  lineage, audit event, and dependency impact report.
- Deleted, consolidated, superseded, retracted, and expired objects are excluded
  from active graph and retrieval projection builds.
- Lifecycle state changes advance the canonical freshness epoch. Retrieval and
  graph queries therefore fail closed until their derived projections rebuild.
- Frozen dossiers are never rewritten. Replay reports lifecycle impacts and the
  successor identity where one exists.

## Operator surface

The authenticated lifecycle API exposes state listing, object dossiers, typed
actions, retention holds, deletion requests, and independent deletion decisions.
Mission Control lists non-active memory and opens its immutable lifecycle and
impact dossier. Mutations remain protected by the founder-intent header and the
control-plane orchestrator credential.

## Verification

- Backend full suite: 260 passed before production deployment.
- Mission Control suite: 45 passed.
- Focused lifecycle, retrieval, graph, and dossier suite: 87 passed.
- Ruff and compileall: passed for changed surfaces.
- Alembic head: `a4e7c9d21f60`.

The production pilot output, deployed merge, live object identities, dossier
digests, rebuilt projection manifests, and final test totals are recorded after
the VM2 migration gate. Rollback restores the prior API image; lifecycle tables
are append-oriented and should be retained unless the migration has never
accepted a lifecycle transition.
