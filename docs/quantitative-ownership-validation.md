# Quantitative computation ownership validation

Date: 2026-08-28

## Result

The ownership corrections for DATA-001 through DATA-003, DISC-002 through
DISC-005, DISC-007, ML-002 through ML-004, RL-001 through RL-002, and RISK-001
through RISK-002 are closed.

`bulletproof_bt` now owns the authoritative scientific producers. The control
plane accepts only their digest-finalized receipts, validates the producer and
milestone contract, stores the immutable envelope, and replays the exact
receipt. It does not recompute the quantitative result.

## Immutable evidence

- Bulletproof producer commit: `597a7697226b82f4c28f5e152c7df1067babba09`
- Bulletproof merge commit: `80db509bfdbfc08c2420f1099650c77a22c7fc4d`
- Bulletproof producer report digest: `5fc1b293fcc0e1cebcdc29fa7fe36b36d0f8ee99a081f650651ce3dae054bb2e`
- Control-plane merge commit: `54c444722d55057a2e8d4b8bdb5845f8dbbb3575`
- Deployed migration: `f4d9b3e57c10`
- Live replay artifact: `docs/evidence/quantitative-ownership/cross-repository-replay.json`
- Live replay artifact SHA-256: `c77c865342facd8f6b2c15bbe94a6c6243b5b6e88e452920fb21c83c54ec7aff`

The live VM2 replay registered and read back 15 receipts. Every replayed digest
matched the Bulletproof-produced digest. The deployed API was healthy after the
migration and exposed the receipt endpoints behind the administrative
credential boundary.

## Verification

- Bulletproof full suite: 1,304 passed, 27 skipped.
- Control-plane backend suite: 628 passed.
- Live VM2 receipt replay: 15 registered, 15 replayed, success true.
- Allocation, capital, order, and promotion authority: false.

## Claim boundary

The deterministic producer fixtures prove repository ownership, schemas,
causal and policy gates, digest finalization, registry validation, and exact
cross-repository replay. They do not prove alpha, data completeness, model
skill, portfolio fitness, exchange readiness, or authority to trade. Those
claims require their own prospectively registered market-data evaluations and
promotion gates.
