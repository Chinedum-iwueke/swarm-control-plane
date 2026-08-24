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

## Operational gate

BT-009 is complete only after VM2 applies migration `e8b1c4d72f90`, the rebuilt
API reports healthy, and `bt009_live_pilot.py` returns a completed bridge, a
completed laboratory publication, 16 registered trials, and a replay transcript.
