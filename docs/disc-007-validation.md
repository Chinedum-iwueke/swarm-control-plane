# DISC-007 Validation

Acceptance covers omitted trials, illegal outcome fields on failed attempts, digest
drift, reduced multiplicity, optional stopping, undeclared researcher degrees,
family-wise/FDR correction, selection-adjusted Sharpe, PBO, immutable supersession and
authenticated route exposure.

Production completion additionally requires migration `d7f1a4b63c90`, a healthy API
and a live no-capital replay showing that a nominal winner can become
`selection_risk_detected` after complete-family correction.
