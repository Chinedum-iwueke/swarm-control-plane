# RI-008 Validation Record

## Implemented

- Allowlisted scientific edge vocabulary with direction and endpoint-type validation.
- Canonical edge provenance, access classification and temporal validity intervals.
- A digest-bound, rebuildable graph manifest and separate node/edge projection tables.
- Access filtering of nodes, edges and provenance before traversal.
- Bounded neighborhood, simple-path and subgraph queries with cycle protection.
- Claim, method, assumption, dataset, run and result evidence contracts and lineage.
- Contradiction, support, review, decision and trial-family overlay predicates.
- Citation-bearing context packs with canonical replay paths and content digests.
- Decimal deterministic mean, sample deviation, Sharpe and max-drawdown calculators.
- Idempotent persisted tool receipts binding inputs, outputs, tool version and context.
- Mission Control explorer backed by the canonical projection with object inspection.

## Acceptance evidence

Validated on 2026-08-12:

- Backend: 224 tests passed.
- Mission Control: 44 tests passed.
- Focused RI-008 and evidence-kernel contracts: 33 tests passed.
- Changed backend and all Mission Control Python surfaces pass Ruff.
- Backend and Mission Control compile successfully.
- Alembic reports one head: `6e8a1c4d9b20`.
- Full migration SQL renders from an empty database through RI-008.
- OpenAPI exposes seven authenticated RI-008 graph/tool routes.

Fixtures cover edge direction, invalid intervals, historical validity, access filtering,
stale projections, cyclic graphs, simple paths, deterministic calculator parity,
idempotent receipts and canonical Mission Control projection use.

## Claims and deployment boundary

This record proves the code and migration contracts. Production projection population
is a separate governed deployment action. After deployment, run the RI-008 pilot and
retain the projection manifest, sampled canonical replay and tool receipt before making
a live-corpus completeness claim.
