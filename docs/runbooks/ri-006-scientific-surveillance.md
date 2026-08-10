# RI-006 Governed Scientific Surveillance

## Boundary

The surveillance service collects metadata and abstracts from the two versioned,
allowlisted feeds in `backend/app/surveillance/approved_sources_v1.json`. It records
fetch failures separately from an empty feed, rejects instruction-like source text,
and never creates a trial, adopts a technique, changes policy, or allocates capital.

Adding or changing a source requires Canon Curator review of its identity, HTTPS host,
rights, access class, cadence, freshness objective, owner, and failure policy. Full text
is not collected through this connector.

## One cycle

Run from the API container or an equivalently configured backend environment:

```bash
python -m app.surveillance
```

The command registers the immutable approved source definitions, polls one source at a
time, retries connection/time-out and 5xx failures at most three times, writes one
receipt per observed attempt result, and creates an idempotent digest snapshot. Place
this command behind a daily external timer only after production source approval.

## Review

Mission Control's Research view shows enabled sources, candidates, weekly digests,
correction/retraction state, deterministic novelty and evidence-quality scores, and
provenance replay. Candidate disposition creates an immutable, digest-bound routing
event. A `propose_question` disposition remains a proposal requiring the existing
research-governance admission path.

## Failure handling

- A failed receipt with `upstream_unavailable` means the feed was not observed; it is
  not evidence that no publications appeared.
- Rejected abstracts remain counted by receipt but are not stored as candidates.
- A correction or retraction creates a new immutable publication linked to its prior
  version; historical decisions are not rewritten.
- Missing fetch receipts make citation replay fail closed.
- Disable the external timer to stop collection. Existing receipts, publications,
  routing events and digest snapshots remain audit evidence.

## Rollback

Downgrade to Alembic revision `0a3c6e85bd20` only before production surveillance
writes, or after exporting the four RI-006 tables. The downgrade removes RI-006 state
and does not alter RI-001 through RI-005 canonical evidence, ingestion, retrieval,
dossiers, backups, or recovery records.
