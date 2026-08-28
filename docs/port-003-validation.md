# PORT-003 validation

PORT-003 preserves the quantitative ownership boundary: Bulletproof produces
construction benchmarks and robust-optimizer evidence; Hermes only registers the
versioned solver and verifies the immutable producer receipt.

## Native producer

- Bulletproof merge: `866e1c1c0ab23b0bb65fa795030eabf1daedfcb1`
- Evidence-bound source commit: `d4080a94149b3a36642562feda853d9403887a87`
- Producer: `bt.institutional.construction.construction_dossier_receipt`
- Solver digest: `4757287e9232b7ebf2ebc7a3fa7c99927164e848e45bff43cc7726cbed54ebcd`
- Receipt digest: `c196ca8f43a1c67c49284b111df44083ba8e076cdb75097b90844ebc5e414825`
- Bulletproof verification: 1,326 passed and 27 skipped; seven focused PORT-003 tests passed.

The native pilot retained equal-weight and inverse-volatility risk-budget
benchmarks, chose the robust optimizer only after deterministic replay,
sensitivity, feasibility and objective gates, and produced weights summing to
one on the configured increment. Its authority flags for allocation, capital,
orders and promotion are all false.

## Hermes deployment and replay

- Registry merge: `ffbb9bc5e39873672d3f260c6fb8a50f07b018c3`
- Migration: `f5e1c7a93b20`
- Backend verification: 633 passed with two existing warnings.
- VM2 API health: healthy after migration and rebuild.
- Solver registry ID: `902a8423-6732-46f3-bd1e-f90b7484a8c3`
- Quantitative receipt record: `63ef6757-137c-4712-9d13-1b4e2b15a4cf`
- Live replay evidence SHA-256: `525f6e0027b5b66c4cece4064d07fb957b9b026821616a4a2d6d3765fba1fe22`

The read-back receipt digest exactly matched the native producer receipt. The
control plane performed no covariance, optimization, benchmark, rounding or
sensitivity calculation.

## Rollback

Retire or stop admitting the affected solver identity and retain its immutable
receipts. Bulletproof then selects the deterministic qualified benchmark. A
rollback never creates weights in Hermes, changes an existing receipt, or grants
allocation authority.
