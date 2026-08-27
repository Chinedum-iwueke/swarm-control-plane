# DISC-003 Validation

- Typed, closed factor-expression AST with explicit units and availability clocks.
- Deterministic bounded parameter-grid compilation and per-trial digests.
- Registered-hypothesis, dataset-manifest digest, and representation-contract boundaries.
- Current-bar leakage, unknown operators, unit mismatch, excessive grids, and excessive expression depth fail closed.
- Immutable source, semantic, and compiled digests with explicit supersession.
- No execution, model selection, promotion, order, or capital authority.

## Production evidence

- VM2 migration head: `e8a2b5c74d10`.
- API image rebuilt from merge `553787a3cea294e5c8daf65a598e266bffcd2844` and reported healthy.
- Registered point-in-time dataset manifest: `f88d456ba2a2585d6c33852296cca8b5e454515cb4a623f8cb61a688110d41f6`.
- Retained representation contract: `dfde67369923bf5eb84d0f248e1ef9297aaf934bebed752cb5f6c3337561b798`.
- Live program: `096bdcf9-4325-48e7-a699-5b1f86ba494a`; compiled digest `09c91fd6710454f1a10acca4d9fc63cc91290495d7bbdac0619c40fb5b3de95e`.
- The live pilot compiled four variants, rejected its unsafe current-bar control, and retained no action authority. The canonical report is `docs/evidence/disc003-report.json`.
- Regression validation: 483 backend tests passed before merge; the dataset-registry hardening suite passed 9 focused tests.
