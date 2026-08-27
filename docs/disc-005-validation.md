# DISC-005 Validation

## Production evidence

- Implementation PRs: #171 and #172; deployed commit `26b4f03ff9cef03df36cc4967cb0f5aa428b71f2`.
- VM2 migration: `a0c4d7e96f30`; API health: healthy.
- Base DISC-003 factor program: `096bdcf9-4325-48e7-a699-5b1f86ba494a`.
- Active AGT-004 policy bundle: `12d23600-6ee5-401b-b43e-0f016641e046`.
- Live run: `f5270d24-15de-4f19-abe0-30f2a38fc7de`.
- Constraints digest: `469e41074848fe9b81a0b2b5db6636574228e51f5b3b4ab7197f554d243fc70f`.
- Candidate outcomes: accepted, duplicate, rejected, rejected; all four attempts retained.
- Exercised violations: forbidden `python_eval`, missing required field, semantic duplicate and nondeterministic generator replay.
- Report digest: `f9128dece18398865bb391c7545166bc1667056392de16703e3ef1083b202526`.
- Full backend suite: 513 passed with two warnings; hardened focused suite: 14 passed.
- Canonical report: `docs/evidence/disc005-report.json`.

## Invariants

- Active data-only AGT-004 policy and active DISC-003 base program required. Read-only `research.retrieve` is permitted; action-bearing tools fail closed.
- Generated output is parsed as data and never executed.
- Operator, field, parameter, node, depth, constant, causality and unit constraints fail closed.
- Model/version/seed/candidate-index output is digest-bound and nondeterminism is rejected.
- Commutative normalization detects reordered semantic duplicates.
- Accepted, duplicate and rejected candidates consume budget and remain replayable.
- Explicit quarantine preserves lineage and removes the generator run from service.
- No execution, result mutation, promotion, order or capital authority.
