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

## Deployment and continued support analysis

Commit `65b5d18` was pushed to main. Both VM1 reviewer services were restarted
at 2026-11-17 11:51:27 UTC after a read-only database query confirmed no queued,
leased or running `alpha_strategy_review` tasks. Both reported `daemon_started`
and subsequent successful `no_work` cycles, with zero automatic restarts.
This deploy is worker-only; no API migration, native-source transition or new
review assignment was necessary. Live candidate review behavior remains untested.

`worker/src/swarm_worker/scientific_support.py` adds bounded binomial survival
calculations and joint-event Frechet bounds. It tests support fragility before
expensive estimator simulation. For 850 rows and a 40-event floor:

| Assumed event probability | Interpretation | Probability of reaching floor |
| --- | --- | --- |
| .05 | Ideal fixed 95th-percentile threshold | .67493 |
| .0475 | 5% independent event loss | .54661 |
| .045 | 10% independent event loss | .40874 |
| .04 | 20% independent event loss | .16713 |
| .10 | Ideal fixed 90th-percentile threshold | .999999995 |

This assumes IID Bernoulli events and fixed eligible opportunities. It does not
estimate a fitted training quantile's held-out event rate, clustered counts,
ties, market drift or data-dependent row selection. Event-loss rows concern loss
of qualifying events, not proof that the minimum eligible row count survives.
For two .67493-probability gates, without assuming gate independence the joint
probability is bounded by .34985 and .67493. Neither primary/rival nor validation/
test gate independence is established. These are conditional mathematical bounds,
not calibrated market probabilities or scientific acceptance probabilities.

Reproduce the first row without reading any lake data:

```bash
PYTHONPATH=worker/src worker/.venv/bin/python - <<'PY'
from swarm_worker.scientific_support import event_floor_probability
print(event_floor_probability(rows=850, floor=40, event_probability=.05))
PY
```

The nominal 42.5 events is an expectation, not a reliable support guarantee.
This supports retaining the robustness objection; it does not authorize changing
q, event floors, windows or the question. A correction must assess support
probability alongside power and explicitly retain the unchanged-method rejection.
The exact candidate estimator, bootstrap and scientifically justified effect
threshold remain outstanding. No offline calculation has been published as an
independent approval receipt.
