# RI-007 Existing-Corpus Synchronization

## Boundary

RI-007 reconciles four bounded source lanes into canonical research evidence:

- the configured Mission Control founder inbox;
- imported prior results placed in `imported-prior-results/`;
- legacy Hermes research documents;
- the bounded Bulletproof research-memory projection.

It never crawls arbitrary paths, promotes reconstructed legacy chunks as primary
evidence, silently deletes evidence, or copies the raw Bulletproof data lake.

## Founder inbox

Mission Control's **Refresh inbox** action scans only the configured inbox and the
approved PDF, Markdown, and text suffixes. Each eligible file is content-addressed,
quarantined, processed by scientific ingestion, and then included in a complete
`corpus-sync-v1.0.0` inventory. The response includes the coverage digest and the
retrieval-projection rebuild receipt.

Renames reuse the canonical digest. Replacements create a new canonical ingestion
and retain the previous item as a predecessor. Files absent from a later complete
inventory become `superseded`; their canonical evidence is retained.

Mission Control maintains a derived `research-inbox-sync-v1.json` index in its private
data root. Unchanged canonical files take a stat-only fast path and are not reread,
rehashed, encoded, or uploaded. New and changed files are hashed; renamed canonical
content reuses its digest-bound receipt. Every completed item is checkpointed
atomically, and a concurrent refresh is rejected. Inspect progress with
`hermes-mission-control sync-status`. Quarantined and failed entries remain retryable.
Projection recovery runs once after a batch only when new canonical content was
published. Deleting this local index is safe but forces a full bootstrap scan; it does
not delete canonical evidence.

## Legacy inventory

After deploying the API migration, inventory legacy rows with the protected operator
environment:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
.venv/bin/python scripts/ri007_corpus_sync.py inventory-legacy
```

A legacy row whose original digest is already present in canonical quarantine is
classified `canonical`. A row with only derived chunks is `excluded` with a recovery
reason. Recover it by placing the original artifact in the approved inbox lane and
refreshing; do not relabel its derived text as a primary source.

## Bulletproof projection

Run the existing `research_memory_sync` named workflow. Registration now canonicalizes
the bounded text projection and records a corpus-sync receipt before reporting task
success. The response carries canonical object IDs. The multi-gigabyte SQLite/raw
research memory remains read-only in Bulletproof and is never copied into Hermes.

## Recovery and rollback

The migration is additive. Rolling back the API removes only reconciliation tables;
canonical evidence and legacy rows remain intact. Restore evidence with the RI-005
corpus backup route and rebuild projections before accepting retrieval traffic. Compare
the restored corpus digest, projection digest, and RI-007 coverage digest to the saved
receipts.

## Completion evidence

A production corpus is reconciled only when every eligible current item has one of:
`canonical`, `quarantined`, `duplicate`, `superseded`, or `excluded`; `failed` is zero;
sampled scientific coordinates replay; and an RI-005 restore/projection rebuild returns
the expected digest. A passing unit suite alone is not a production migration claim.
