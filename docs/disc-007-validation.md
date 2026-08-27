# DISC-007 Validation

Acceptance covers omitted trials, illegal outcome fields on failed attempts, digest
drift, reduced multiplicity, optional stopping, undeclared researcher degrees,
family-wise/FDR correction, selection-adjusted Sharpe, PBO, immutable supersession and
authenticated route exposure.

Production completion additionally requires migration `d7f1a4b63c90`, a healthy API
and a live no-capital replay showing that a nominal winner can become
`selection_risk_detected` after complete-family correction.

## Completed evidence

- Implementation: PR #162, merge `91e88dfcc879d5d19e68af3decde61b1a82f063f`.
- VM2 pilot compatibility and canonicalization: PRs #163 and #164, ending at
  `0721f1c4d487c7f98dd670c98b268c67bf0958fa`.
- VM2 migration: `d7f1a4b63c90`; rebuilt API healthy with the authenticated audit route.
- Full backend suite: 475 passed with two warnings; focused DISC-007 suite: 13 passed.
- Live report: [`evidence/disc007-report.json`](evidence/disc007-report.json), file
  SHA-256 `b29bd406cf374bd1ca2788963b693643dd809e9865cd717e4378303f07a09dc2`.
- The live complete-family audit retained two completed, one failed and one cancelled
  trial. Nominal winner p-value `0.02` became family-wise p-value `0.08` and conclusion
  `selection_risk_detected`.
- Report digest: `bad4c9db76f3aceec9a06cc8652519707c517e5e223e3434f56a9867b71ed8a0`.
  No promotion, execution, order or capital authority was granted.
