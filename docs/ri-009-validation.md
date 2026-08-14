# RI-009 Validation Record

## Implemented

- Immutable, versioned domain curricula bound to retrieval and graph corpus digests.
- Acyclic topic and prerequisite maps with canonical evidence anchors.
- Explicit source-authority, distinct-source, quarantine, and opposition rubrics.
- Held-out answerable and mandatory abstention cases.
- Measured retrieval recall, citation fidelity, opposing-evidence recall, abstention
  accuracy, cross-domain leakage, and topic coverage.
- Fail-closed qualification when projections, corpus, graph, or evaluation are stale.
- Retained evaluation cases, thresholds, metrics, digests, evaluator, and review cadence.
- Mission Control readiness rows with explicit blockers rather than an expertise label
  derived from upload volume.

## Acceptance evidence

Validated on 2026-08-14:

- Backend full suite: 234 tests passed.
- Focused RI-009 and RI-008/retrieval suite: 37 tests passed.
- Mission Control suite: 44 tests passed.
- Changed Python surfaces pass Ruff and compile successfully.
- Alembic has one head: `c4a8e2d71f30`.
- Full migration SQL renders from an empty database through RI-009.
- Contract fixtures cover cyclic prerequisites, unknown fields, mandatory abstention,
  positive qualification, opposing evidence, citation identity, and cross-domain
  leakage failure.
- A production-scale RI-008 pilot reproduced PostgreSQL's 65,535-parameter ceiling;
  graph traversal was changed from whole-corpus ID materialization to access-filtered
  bounded frontiers and a regression test verifies bounded query parameters.

## Claim boundary

This record proves source behavior and migration compatibility. Production deployment,
registration of the first systematic-research curriculum, and a held-out live-corpus
evaluation are separate evidence gates. Until they pass, the senior quantitative
researcher is not described as domain-qualified by RI-009.
