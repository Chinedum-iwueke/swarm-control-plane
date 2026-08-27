# ML-004 Calibration, Uncertainty and Abstention

ML-004 qualifies the uncertainty behavior of a model candidate already selected by
ML-003. It reuses ML-001's held-out calibration and inference-receipt machinery; it
does not introduce a second fitter or grant activation, promotion, or capital authority.

## Contract

Each immutable assessment binds an ML-003 evaluation, a qualified candidate, and an
RI-004 evidence dossier. The submitted specification carries a held-out calibration
method, complete reliability bins, a conformal or block-bootstrap uncertainty contract,
applicability slices, a non-causal explanation receipt, and an explicit abstention policy.

The service recomputes expected calibration error and verifies four mandatory inference
scenarios: supported input, miscalibration, distribution shift, and low support. A model
must abstain with the correct reason outside its validated envelope. Miscalibration,
undercoverage, misleading explanation fidelity, incorrect applicability labels, or an
incorrect abstention receipt changes the assessment to `demotion_required`.

## Operations

Apply migration `e6c1a4f83b20`, rebuild the API, then run:

```bash
python worker/scripts/ml004_pilot.py --output /var/lib/invariance-swarm/ml004/report.json
```

The pilot is deterministic contract evidence only. It is not evidence of predictive
performance and cannot activate a model or authorize trading.

## Rollback

Stop creating new ML-004 assessments and route inference to the previous independently
validated ML-001 calibrated bundle or registered baseline. Existing assessments remain
immutable audit evidence. Downgrade the migration only after confirming no assessment
records require retention.
