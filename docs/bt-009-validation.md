# BT-009 Governed Research Bridge Validation

## Scope

BT-009 connects a founder-approved, structured research proposal to the existing
Bulletproof native engine and then publishes the resulting immutable evidence
through Hermes. It does not grant capital, live-order, self-approval, or
production-promotion authority.

## Implemented contract

- Plain-English normalization is explicit and digest-bound.
- The existing `l7_h1_csi_gated_displacement_trend` strategy is resolved without
  generating duplicate strategy code.
- Tier 2 is resolved explicitly to Tier2B.
- The registered Cartesian grid contains exactly 16 variants and uses an
  exhaustive stopping rule.
- Every variant runs through the native classic engine. The deprecated fast path
  remains disabled.
- All 16 runs pass the native truth gate and finalize atomic run bundles.
- Hermes retains the proposal and monotone lifecycle receipts.
- The registry receives all 16 trials before result publication.
- Statistical and adversarial reviewers are distinct from execution.
- The selected negative result remains canonical evidence.
- Publication completes only after current graph and retrieval receipts and a
  Bulletproof research-memory receipt exist.

## Source validation

- Control-plane backend: `304 passed`.
- Governed bridge, laboratory publication, and knowledge graph focus: `24 passed`.
- Bulletproof governed bridge, atomic bundle, and laboratory focus: `26 passed`.
- One additional atomic-bundle schema test is blocked in the host system Python
  because its preinstalled `jsonschema` predates `Draft202012Validator`; the
  failure is a dependency mismatch rather than a bundle validation failure.

## Qualification evidence

The final qualification is bound to Bulletproof commit
`7010c4d8c151ec77406386192ffb620dead30183`.

- Registered variants: 16
- Truth-gate status: `PASS`
- Truth-gate warnings: 0
- Truth-gate hard failures: 0
- Search-plan digest:
  `ad9ed73302b25837ae304ebde9e2fb14a85c6cb529011aa034063ba26dc34964`
- Dataset digest:
  `3fc0245b59f76a91891b90dbeaa55e141761020957dbec17fdabc0b4b0c1f93f`
- First registered result: 8 trades, net expectancy `-0.79429141974 R`
- Production eligible: false

The negative result is intentional validation evidence: BT-009 proves the
governed research lifecycle, not a profitable market claim.

## VM2 operational replay

The genuine VM2 replay completed on 2026-08-24 against healthy API image
`invariance-swarm-api:0.4.0` at Alembic head `f1a6d3c84b20`.

- Governed bridge: `649158a6-10a4-5ae6-9872-00e0ff1e4aa4`, state `complete`
- Laboratory publication: `5cbafb3e-f3e7-5f1a-9678-278368d971fe`, state
  `complete`
- Publication events: four ordered, digest-bound events from
  `canonical_committed` through `publication_completed`
- Registry lineage: 16 trials, one retained result, two independent reviews,
  and one founder/operator decision
- Selected bundle:
  `293424d8e8923568bb2150dfaea2cdfaf1153ba3d5b87925aa99fd3999688720`
- Canonical receipt:
  `4ac5045e99d5c2acbc6cead7b3407e9d1146c305c26e72bffabd762fbd3a9efb`
- Canonical objects: one run, one result, two reviews, one decision, and one
  episode
- Knowledge graph: source epoch `577345`, 784,222 nodes, 1,368,759 edges,
  manifest digest
  `d3c8d5fb917f3954a4cae1ceebeba6e6e29a415199003fe28ec330bacb190d8f`
- Retrieval projection: source epoch `577345`, 783,417 objects, corpus digest
  `0209d8b90319772a0af5253a5ec254c6e6692f4ff8343855cc40fd3ef740c6eb`
- Bulletproof memory: one publication row with receipt digest
  `9d3bf02ecc2758ff74e8b2adbccce7b1e9043f85b051206411d1ef818440bed8`

The replay also exercised interruption-safe resumption across registry,
publication, projection, and memory boundaries. Live defects found by the replay
were fixed in PRs #92 through #97, including authoritative-lineage recovery,
canonical result support, typed evidence hashing, and serialized publication
event allocation. No live-order, capital, self-approval, or production-promotion
authority was introduced.
