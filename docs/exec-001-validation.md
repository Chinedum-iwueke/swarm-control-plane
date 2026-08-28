# EXEC-001 validation

Bulletproof is the authoritative producer of canonical execution events and
point-in-time journal reconstruction. Hermes registers the immutable event schema and
verifies the producer receipt; it performs no event ordering or execution-state
calculation.

- Bulletproof merge: `22e0bda5d7160db49b864db2d3400596d3b814c7`
- Evidence-bound source: `0a48a320200c9841dee804ad0990269c01981ddd`
- Hermes registry merge: `8e53f9350030477899ce1849abe6d532a6920f20`
- Migration: `f8c2d4a71e90`
- Native verification: 1,334 passed and 27 skipped; eight focused tests passed
- Hermes verification: 637 passed with two existing warnings
- Event schema ID: `c596717e-0733-4e70-8c12-91ccb730ff8b`
- Event schema digest: `b3355f730326b7bb355a32b3b341145f30844587e29dcb62447af7bad8a9c6f6`
- Receipt record: `5cab237f-bc51-4a13-b8ef-c8426fd3da5d`
- Receipt digest: `63e1a21d355c72b841ea7d6366859e098d369551c2623a5e805de8663a3a3a5c`
- Replay digest: `ff486a4f97df5cd10873c12291b826d28ac42b79aed2b2ecc35bec2805c88218`
- Live evidence SHA-256: `0120133b547263428df409d5b5ffbbef5edb09fcd28b5be652e5bbbb37864bfc`

The deterministic pilot ingested source sequences 1, 3 and then 2. It surfaced the
temporary gap and late arrival, then reconstructed a gap-free deterministic projection.
This validates contracts and replay, not exchange connectivity or market performance.
No allocation, capital, promotion or order authority was granted.

Rollback stops admitting the affected schema version, retains the append-only journal
and rebuilds projections from a previously admitted schema. It never edits historical
events or silently guesses sequence order.
