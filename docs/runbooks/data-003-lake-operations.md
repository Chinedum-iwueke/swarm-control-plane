# DATA-003 Lake Operations

## Boundary

DATA-003 governs DATA-002 metadata and read-only source references. It never embeds
protected rows in prompts, decisions, events, or evidence and never mutates source
partitions. An immutable governance snapshot binds one catalog digest, quality SLOs,
lineage, entitlement rules, storage budgets, retention holds, recovery manifests and
derived publications.

## Decisions

Admission checks the exact partition against schema, duplicate, gap and freshness SLOs;
default-deny principal/action/purpose entitlement; active retention holds for deletion;
and storage budget state. Every decision is appended to a digest-chained metadata-only
event ledger. Warning capacity remains observable; exhaustion fails closed.

## Recovery

A quality incident can disable a derived publication without changing its source or
catalog. Restore requires the publication to be disabled, an integrity-verified recovery
manifest, the exact catalog digest and the exact restored source-object set. Rollback
selects the last verified manifest; it does not rewrite history.

## Routes

- `POST/GET /v1/research/lake-operations/snapshots`
- `POST /v1/research/lake-operations/admissions`
- `POST /v1/research/lake-operations/publications/disable`
- `POST /v1/research/lake-operations/publications/restore`
- `GET /v1/research/lake-operations/events`

The service grants no source-write, execution, order or capital authority.
