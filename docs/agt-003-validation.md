# AGT-003 Validation

- Backend: 393 tests passed.
- Worker core service: 18 tests passed on Python 3.12.
- Migration: clean PostgreSQL 16 upgraded through `b3e7a1c52d90 (head)`.
- Contract tests cover valid DAGs, cycles, unknown dependencies, duplicate nodes, attempt-budget overflow, canonical digesting and cooperative cancellation.
- VM2 runs migration `b3e7a1c52d90` and healthy image
  `sha256:598ed40a60b22798e7d1640e396be4c2725b4bf9fb77901cf7db134afc3a11b5`.
- The live two-node no-execution pilot finished `cancelled` as designed. It retained
  manifest digest `ef38ec20fddc92080db2a2b85392c92dc4278769a2968ca994f1ed56a3556463`,
  event-chain head `d52646f5f0a7f3daade23a9503d261a0490f55b68aa94eb44c20644897fc81a1`
  and report digest `3db36e82c88622629381137bf89ce072620489b9027f677609ee1cae8a614295`.
  It had no execution or capital authority.
