# AEP-007 calibration budget redesign

Status: prospective proposal, not approved execution authority. Prepared November
23, 2026 after the founder selected the budget-redesign direction. No existing
mandate, campaign, scientific specification or resource counter is changed.

## Retained evidence

Source: Bulletproof `e0924587eb5df8bee0d876312a2c713feead462f`.
Method task: `2a91240b-19b5-45ec-b4c8-1a7c364e10b5`.
Verified result: `c0531c2e5d603be0256e92853338187eba2dcbe9bceb3eb305ab1d009a4e720d`.
Specification review `11640223-9621-4a04-b38c-6a0d6732efe8` accepted;
causality review `72022000-4c48-4f62-bf60-22c302818837` rejected calibration
precision. R3 closed with zero trials and exhausted its author/diagnostic budget.

The BTC question, four variants, estimators, support minima, partitions,
coverage windows and 10,000 inner replicates remain unchanged. Larger calibration
does not imply predictive value or acceptance of the scientific design.

## Prospective arithmetic

For independent Bernoulli outer outcomes, the retained pointwise two-sided 95%
Clopper-Pearson interval has worst-count half-width 0.44864846 at n=3,
0.10014999 at n=103 and 0.09966107 at n=104. Thus 104 is the minimum draw count
meeting half-width <=0.10 for every success count. This is not a simultaneous
coverage guarantee, power result, or a guarantee that draws meet support rules.

Recomputed from every stage in the verified R3 workload:

| Work unit | Prospective count | Existing cap | Proposed cap |
| --- | ---: | ---: | ---: |
| Statistic evaluations | 266,240,000 | 8,000,000 | 266,240,000 |
| Complete histories | 65,936 | 65,536 | 65,936 |
| Full-functional evaluations | 308 | 320 | 320 (unchanged) |
| OLS fits | 20,445,568 | 21,233,760 | 21,233,760 (unchanged) |

Derivations:

```text
statistics = 4 scenarios * 104 draws * 2 partitions * 4 variants
             * 2 statistics * 4 block analyses * 10,000 replicates
histories = 4 * 8,190 solve + 4 * 8,190 verification + 4 * 104 outer
functionals = 4 * 4 Newton iterations * 19 evaluations + 4 final evaluations
OLS fits = 4 * 8,190 * 8 * (4 * 19 + 1 final + 1 verification)
           + 4 * 104 * 8 outer fits
```

Counts describe the retained declared algorithm, not independently verified
implementation cost. Retry, failed-support replacement, additional solver starts
or extra diagnostics cannot be silently added. Any such work must be accounted
for separately and stay inside explicitly authorized bounds.

## Required implementation boundary

`bt/governance/design_adequacy.py::assess_design_adequacy` currently limits the
prospective calibration declaration to 10 million units. A source-bound change
must distinguish a static design budget from permission to execute it.
Do not raise the worker's execution reservation limit to match the declaration.

`bt/governance/diagnostic_tools.py::run_diagnostic` returns
`structured_calibration_executor_unavailable` for the structured experiment.
The legacy residual probe must not be relabelled as this experiment's executor.
Implementing and validating that executor requires separate engineering authority.

Required regression checks: large static declarations perform no calibration;
existing execution limits still reject oversized reservations; malformed or
overflowing factor products fail closed; identity and evidence binding survive;
uncounted retries and changed algorithm factors invalidate the approved estimate.

## Safe estimation and commissioning sequence

1. Review this prospective budget and the precision interpretation independently.
   Freeze a corrected specification only after the review accepts it.
2. Bind any static-validator repair to a new source and fresh exact-digest
   authority. Preserve R3 and its charged counters unchanged.
3. Under separate engineering authority, implement the actual structured
   calibration with deterministic seeds, streaming histories, checkpointed
   scenario/draw identifiers, idempotent accounting and terminal failure receipts.
4. Test the executor with synthetic fixtures before a separately authorized
   timing probe. The probe must exercise real solver/OLS/bootstrap kernels;
   a trivial random-number benchmark cannot estimate this workload.
5. Specify probe CPU, memory, wall-time and work-unit limits before launching it.
   Measure peak RSS, CPU time and throughput by work unit. Extrapolate phases
   separately and report uncertainty; do not sum incompatible unit rates.
6. Present the measured resource estimate and an execution plan for separate
   exact-digest approval. Use one campaign initially, bounded chunks, durable
   counters and a watchdog. Stop on budget, memory or deadline exhaustion;
   incomplete calibration is inconclusive, never a pass.

No duration estimate is currently justified. No large calibration, market-data
backtest, order, capital allocation or promotion is authorized by this proposal.
Do not spend another author call merely retrying the unchanged eight-million cap.

## Local repair verification

The prospective declaration bound is now aligned locally with the assurance
ledger's existing finite integer bound of 10^15 in Bulletproof, the API and
worker shape checks. This is a serialization/validation bound, not an approved
experiment budget. The legacy native execution ceiling and worker episode
execution reservations remain at ten million; individual approvals may be lower.
The structured experiment still requires its own executor.

Regression tests cover rejection of invalid declaration types and bounds, API
and worker shape parity, no random generation or bootstrap calls on an
over-budget execution request, and refusal to route structured designs into the
legacy marginal probe. This repair is local and uncommissioned; it does not
change the source pinned by existing mandates.
