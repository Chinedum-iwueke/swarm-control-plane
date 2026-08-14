# RI-011 Production Retrieval Validation

RI-011 was production-qualified on 2026-08-14 against the live canonical
systematic-research corpus. It preserves the RI-009 confidence and abstention
contract while replacing corpus-wide request work with constant-time freshness
checks and bounded, indexed candidate generation.

## Deployed contract

- Control-plane merge: `2801e4b7aefccda286487f8ae77641c6857e4f7e`
- Alembic head: `f1a6c8d42e70`
- Projection: `hybrid-retrieval-v1.1.0`
- Corpus: 623,375 projected scientific objects at freshness epoch 1
- Candidate policy: 100 ranked conjunctive candidates, 500 bounded disjunctive
  candidates, and at most 100 graph neighbors
- Search capacity: eight concurrent requests with bounded admission
- Calibration: unchanged `evidence-confidence-v1`

Authorization constraints are part of every candidate query. Candidate text is
not loaded before project, access-class, schema-version, scientific-type, and
request-project filters have been applied. Selected results are re-authorized
against canonical evidence and fail closed on digest or freshness changes.

## Freshness and indexes

Statement-level database triggers advance a canonical corpus epoch and rolling
digest after evidence-object, edge, or alias mutations. Retrieval status and
queries compare this snapshot to the projection source epoch in constant time.
The deployment adds indexes for content digests, authorization scope, aliases,
and PostgreSQL full-text search.

Projection construction remains an offline deployment operation. The live
623,375-object rebuild completed before the API was recreated, so readers stayed
on the previous compatible projection until the new projection transaction
committed.

## Live benchmark

The declared thresholds were fixed before the production run:

| Measure | Threshold | Observed |
| --- | ---: | ---: |
| Warm p95 | 2,000 ms | 564.253 ms |
| Concurrent p95 | 5,000 ms | 1,228.084 ms |
| Concurrent workers | 4 maximum | 2 |
| Maximum hydrated candidates | bounded | 530 |
| Evidence answer correct | required | yes |
| Unknown-identifier abstention correct | required | yes |

Benchmark digest:
`091826f949083cad09c2caee688b2a04af5e63f4e10490b853e7af7a32c3fe63`.

Two failed production observations were retained during optimization. The first
hydrated about 4,000 rows and measured 10,285.742 ms warm p95. Bounding hydration
to about 500 rows reduced memory work but still measured 8,904.366 ms because
PostgreSQL ranked the full broad-match set before limiting it. The final
two-tier query uses the GIN index to select a precise conjunctive tier and a
bounded unranked partial-match tier before model-independent Python fusion.

## Independent evaluation

Systematic-research curriculum `6470d401-da23-440c-8c48-42d3820b7614` was
reevaluated as immutable version `1.0.2` after deployment.

- Evaluation ID: `bb427da9-3fe4-4d25-a98d-e0b7e3fa08a4`
- Status: `qualified`
- Record digest:
  `addc87a5aa691cc414f66d8a68434860776a836fc6f95ba5afe238564469a603`
- Retrieval recall, citation fidelity, opposition recall, abstention accuracy,
  and topic coverage: 1.0
- Cross-domain leakage: 0.0

No LLM judge was introduced. Candidate generation, fusion, confidence, and the
evaluation oracle are deterministic and versioned.

## Verification

- Backend suite: 246 passed, 2 dependency deprecation warnings
- Focused retrieval suite: 25 passed
- Ruff: passed
- Compileall: passed
- VM2 API: healthy after recreation
- VM2 migration: `f1a6c8d42e70 (head)`

Rollback restores the prior application image while retaining the canonical
corpus and immutable evaluations. Downgrading the migration removes only the
derived indexes, freshness trigger/state, and projection source epoch; canonical
evidence is not deleted.

