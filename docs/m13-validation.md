# M13 Closed Five-Agent Pilot Validation

Status: complete. Exit gate passed on 2026-08-01.

## Implemented

- Five distinct role packages, permission profiles, capabilities, and agent identities.
- Agent-authenticated research proposal, specification, result, and review endpoints.
- Active-package and capability checks at every role endpoint.
- Immutable data-snapshot registry linked to experiment manifests.
- A digest-bound 8,760-row real Binance BTCUSDT hourly snapshot.
- Restricted real-data signal execution in the existing isolated Git worktree.
- Founder approval before execution.
- Separate statistical reproduction and adversarial audit identities.
- Two distinct reviews required before a founder decision.
- Complete positive or negative trial retention and related-hypothesis search.
- Production eligibility fixed to false.

## Automated verification

- Backend: 69 tests passed (two upstream deprecation warnings).
- Worker: 171 tests passed.
- All five local role packages and workflow digests validated.
- Ruff and compileall passed for the changed M13 and registry surfaces.

## Production evidence

- implementation source commit: `b89df43919963ac262c5814d8f2f4afaf2636eb6`
- registry repair commit deployed on VM2: `023c8c8923386fa1f7f7f849a8b814178a132d83`
- migration head: `e5f7a9b1c330`
- senior agent: `e7efef83-5772-49b2-8d0b-f3873e3f58d0`
- specification agent: `8c9e7be6-eff1-45ae-a2f8-5e8b109052ae`
- execution agent: `440f8ec9-8a88-4338-acb4-da3d948701b8`
- statistical agent: `2fa1c48d-20e8-429d-a1ce-947d299ad321`
- adversarial agent: `8bb10dc1-a47f-4616-bb79-a067db0c7021`
- snapshot: `232e47cf-a74c-4387-896e-f57dcc719f56`, digest
  `87ccd7a65daccae64bdea86a321cf9f114370e5857e61cfcaa5306bb5a1bdbf1`
- brief: `d4b36822-bd16-4f2c-ab0c-e6e5c0bf2938`
- hypothesis: `dbfb3e4a-f371-41f3-8a6b-607f813b1c54`
- experiment: `010b9dad-d726-4016-8df4-43ded8ed3eef`, digest
  `8d5937085da7dfdb8a08064f54060765e5f639d589d59f29c96f2d6c4de76668`
- trial: `ab2c3758-2cb9-4f53-8cfe-81ce8e62d98d`, digest
  `1ba9b3cc9f5a7f1c82f37899e9ef4134f7dd170df8ce527a48b873306c594ce4`
- task: `11bdfd21-8cb9-4439-8031-5dc3ba542a66`, succeeded in one attempt
- founder approval: `24491257-dd74-437e-bc4d-4a2674ec2357`, plan digest
  `70cff938a406ab5a7c90f19fb34b54459556734150b185bf627a4099e7aa7de2`
- result: `b5516a25-aa83-4a74-99eb-71664f7eb672`, rejected, digest
  `a22781c0577b63aab6acb95b7cc435626fe476b5d92e8958e6f2103f346415b8`
- statistical review: `7625f80e-fa34-44b1-8962-290b049877ae`
- adversarial review: `f0e88f7d-4241-4d8b-a02e-6156238c7a81`
- founder retention decision: `f3567fce-a94a-4924-9895-d52cc26fcc8f`
- exact reproduction: true; trial-family count: 1; related hypotheses found: 2
- attacks: buy-and-hold Sharpe `-1.35641969`, doubled-cost Sharpe
  `-9.79729074`, lag-stress Sharpe `-5.39438523`
- production eligible: false; single-period limitation: true
- evidence SHA-256: `724caacfad009a2e8bff8e0afd45f095a24e9e00fac59ab56fd15740ab17fbd9`
- audit SHA-256: `1021d7b79b405e546a26df90fd07fa6f27c72bde546d50275235d1df479a9bd4`
- report SHA-256: `2a2c8277bbff1f0588bd2d2f639e8808253c6626153856d180d55924a38346c7`
- retained workspace: `M13-REAL-DATA-20260801T135051698919Z-11bdfd21-8cb9-4439-8031-5dc3ba542a66/attempt-1`

## Exit decision

M13 exits only when the founder-approved real-data trial is executed once, independently
reproduced, adversarially reviewed, retained regardless of outcome, and searchable.

Decision: **GO**. M13 passed every exit condition. The signal itself was rejected and
remains explicitly ineligible for production, which demonstrates that the loop retains
negative evidence rather than optimizing or promoting it away.
