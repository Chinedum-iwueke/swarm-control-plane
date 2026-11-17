# Offline precision and review-scope assessment

Date: 2026-11-17. Status: synthetic sensitivity checked; scientific adequacy and
end-to-end execution **not certified**. This is an engineering assessment, not a
replacement independent review or an approval receipt.

## Frozen evidence

- Campaign: `13a791af-9918-47c0-b924-07bfbf5ffb6c`, completed without a candidate
  and with zero trials.
- Candidate: `bfefd78f-113e-4383-beeb-1ba964a8622d`.
- Subject: `999a892385cb42b85633171bd4bc19b28d78ca01f11f065519dfb3ed8a981795`.
- Route: `96cb6ee4-fcd2-4a2d-a72c-3e31de90284d`.
- Strategy-spec review approved: `bb09de36-c996-4069-9559-e82b8013644b`.
- Causality review rejected: `66dde114-276d-426f-ad07-2c5902510fb6`.

Both review tasks completed operationally. Their scientific verdicts differ.
Neither verdict nor any historical specification is changed by this assessment.

## Reproducible offline sensitivity

`worker/src/swarm_worker/scientific_precision.py` implements a bounded, seeded
normal-contrast sensitivity calculation. The CLI reads no market data, invokes
no model and issues no authority. From the repository root:

```bash
PYTHONPATH=worker/src worker/.venv/bin/python worker/scripts/scientific_precision_probe.py \
  --events 40 --controls 810 --family-size 4 \
  --subject-digest 999a892385cb42b85633171bd4bc19b28d78ca01f11f065519dfb3ed8a981795
```

Repeat with `--family-size 8` for a sensitivity comparison, not a silent change
to the preregistered multiplicity procedure. Defaults: alpha .05, target power
.8, 20,000 draws per cell, seed 42. Effects are in common residual-SD units.
The standard error is `sqrt(DEFF * (1/n_event + 1/n_control))`.
The one-sided threshold uses alpha/family size. This is the Bonferroni/first
Holm threshold, not a simulation of the complete Holm decision procedure.
See the [statsmodels normal-power reference](https://www.statsmodels.org/stable/generated/statsmodels.stats.power.NormalIndPower.power.html)
for the standardized-effect, sample-ratio and one-sided-power parameterization.

| Assumed design effect | 80% minimum detectable effect | Power at effect .25 | Power at effect .5 |
| --- | --- | --- | --- |
| 1 | .4994 | .2426 | .8011 |
| 2.25 | .7490 | .1127 | .4272 |
| 4 | .9987 | .0708 | .2426 |

Family-eight sensitivity raises those MDEs to .5409, .8113 and 1.0817.
The family-four report digest is
`f9244bef3f2a8dc097a8988aeefddc0cd4c80a0bfa27513b3b9cc7bfc5a8cc0e`.
These sensitivity hashes are not scientific approval receipts. The family-eight report digest is
`cc98bf8c99c8cdadb78be3db2e10ce3ce2e73a7902c4996a26ba06405bcd13ae`.

The original .75-1.00 SD arithmetic is supported under its assumptions. The
assumptions are not validated. Gaussian simulation agreeing with the Gaussian
formula is a computational check, not independent market or estimator evidence.
The utility does not model fitted nuisance parameters, actual event clustering,
eligibility losses, paired-rival covariance, random event counts or the exact
block-bootstrap estimator. Full acceptance has additional joint gates.

## Finding-by-finding scope assessment

| Rejection finding | Assessment and required owner |
| --- | --- |
| Precision/power justification for partition and event floors is missing | Legitimate unresolved design obligation. The method designer must justify a meaningful effect scale and dependence assumptions; an independent reviewer must assess them. Correct arithmetic alone is insufficient. |
| Exact window fit and narrow q=.95 event margin suggest fitting minima to coverage | The narrow margin is a genuine robustness concern. Numerical equality alone does not establish outcome-driven selection. Require lineage, derivation and eligibility-loss sensitivity, not an inference of intent from equality. |
| Point-in-time membership and listing/tradability are unverified | Retain as a validity obligation. Identify its evidence source and fail-closed check. If that evidence is indispensable and unavailable, defer; OHLCV availability is not a substitute. |
| Continuity, liquidity, seasonal variance, finite values, rank and event counts are unobserved | These are construction/execution checks. Before authoring, require explicit algorithms and failure behavior. Do not demand completed execution observations merely to authorize writing the checks; reject absent checks or unsupported claims of success. |

The reviewer prompt now distinguishes these phases without automatically
approving anything. This instruction change is not a deterministic adjudicator
and does not erase the real remaining power-design blocker. Historical reviews
remain immutable; any changed scientific method needs a reviewed successor.

## Required next proof

1. Specify a defensible minimum meaningful effect and dependence envelope without
   looking at held-out results or lowering criteria to fit available coverage.
2. Calibrate the exact proposed estimator and primary/rival decision procedure
   under prespecified null and alternative data-generating processes, including
   serial dependence, eligibility loss and sparse events. Measure false-positive
   rate, interval coverage, power and Monte Carlo uncertainty.
3. Attach that evidence to an authorized correction successor for independent
   review. Only an accepted, source-bound successor can enter engineering.

No unchanged discovery retry, new mandate allocation, paid review, market-data
scan, native backtest or production approval is part of this offline increment.
