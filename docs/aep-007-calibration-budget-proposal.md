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

The prospective declaration bound is aligned with the assurance
ledger's existing finite integer bound of 10^15 in Bulletproof, the API and
worker shape checks. This is a serialization/validation bound, not an approved
experiment budget. The legacy native execution ceiling and worker episode
execution reservations remain at ten million; individual approvals may be lower.
The structured experiment still requires its own executor.

Regression tests cover rejection of invalid declaration types and bounds, API
and worker shape parity, no random generation or bootstrap calls on an
over-budget execution request, and refusal to route structured designs into the
legacy marginal probe. Bulletproof source `6f3df74` now carries this repair in
the separately approved commissioning lineage. Existing mandates retain their
original source bindings.

## Commissioning outcome and budget-binding repair

Mandate `a65b4880-1596-431d-a354-a85f8fa772d6` and campaign
`9665c675-6eab-4cf1-b007-452037a0f690` received separate founder approvals.
The first task `ef64fe54-44c8-4f32-b1db-f30d997aaba7` passed structural diagnosis
without authoring because the operator-prepared findings envelope used the wrong
schema. Both reviewers rejected the unchanged three-draw design. The controller
automatically created correction task `8c6a5b71-b260-4284-85c8-4cc84ca64ba9`,
preserving remaining calls and the original deadline.

That task reserved one author call and one diagnostic, then stopped with
`invalid_stage_result`: the initial proposal still froze the old caps, conflicting
with the newly authorized cap instructions. The episode correctly refused a
model-originated cap change. The campaign closed with zero trials; task-level
success here means publication of the blocked episode, not method acceptance.

The local repair adds a prospective-budget amendment constructor and matching
API/worker checks. A new successor must bind approved caps into its initial
proposal, retain the parent proposal digest and old caps, and receive separate
exact-digest activation. Runtime cap immutability remains unchanged. Existing
contracts gain no fields or changed serialization. 107 backend tests and 48
worker tests passed. The amendment repair was subsequently deployed as
`7167881`; audit transport alignment followed in `1a79885`, and explicit
operative-definition invalidation in `fb26f74`.

The retained correction document
`2a32ed349d3f3ba53392155378fbe89da3b3f49550ad09cab5c991b14cc7d4e2`
contains the revised 104-draw method. A read-only prospective replay, changing
only its two authorized caps, returned no native structural findings, with
65,936 histories, 308 functionals, 20,445,568 OLS fits and 266,240,000 statistics.
No original artifact was rewritten. This supports preparing a no-new-author-call
successor for fresh independent review; it does not establish scientific
acceptance, executed calibration, engineering or backtesting.

## Accepted amendment-consistency method (2026-11-23)

Campaign `8799a2ef-4239-4079-89e4-58f1318ba8dc`, separately activated under
mandate `202f4582-0e57-4648-ac09-65e901d3f936`, completed correction task
`8f5784b9-21b7-45f8-b9ed-8b2c0fcb0f0d`. Its verified method packet is
`b84147a349a10e7c0d30e005d19bb83d82799983f935e460c9e426bfc738f9d2`.
Both independent review tasks accepted this exact packet with no findings:

- `624176c9-c731-4acd-9b61-062dfd8ce800`
- `4c022029-a23c-4a5d-a4a6-5ca70f71034c`

The live campaign next action is `materialize_accepted_method_handoff`.
Acceptance establishes pre-execution specification adequacy only. Neither
review establishes empirical calibration, numerical feasibility, sufficient
observed support, power, scientific qualification or profitability.

The campaign remains method-only: engineering and backtests have not started.
The next handoff requires a successful governed native planning task at
`6f3df74`, not just the retained read-only planning replay. The older planning
task `cae83a9d-314b-4c46-a5f7-dff06a6f3d20` belongs to the previous source.
`alpha_method_engineering.verified_plan_evidence` checks task success, source,
candidate identity, receipt custody, exact reviewed report and engineering
template agreement before materialization.

Mandate `6d530aac-bb03-4fa7-9f8c-7f60888edb13` subsequently received exact-digest
founder approval. It permits current-source plan revalidation and separately
approved synthetic-test engineering; it does not authorize real-data calibration
or market-data backtests.

The first planning task `1a8f7699-721a-4730-8213-2c2d5940d73c` failed closed:
replacing the admission binding without rebuilding its bound coverage package
caused `coverage receipt identity or digest mismatch`. No model call occurred.
The historical failure remains intact. Governed single-panel re-attestation
`b4752d0e-ca1a-44a9-a030-7eb4c5baf147` then succeeded. Its planning successor
`ed1312dc-1395-4351-a146-f77340de334f` produced a custody-verified ready report
`3ed4c16ee285696ece75d8dc9c6c39568ed77f9e79c332da419f4e4c572ac886`
with no rejection reasons and unchanged smoke/scientific partitions.

Successor campaign `7263fc0e-f885-43b3-8e98-1eeb99081812`, digest
`8197a450b6f79211882de89c5a0e3191108259a8450b5605af90b3eb62fa2038`,
received separate activation approval. It binds the new planning receipt,
one static refresh, fresh independent handoff reviews and separately approved
synthetic-test engineering. Engineering has not started. The 55 focused
method-engineering and requirements-handoff tests pass.

The static refresh task `f257936f-7141-4052-bacc-1cfe99ac9f23` completed;
review tasks `585b087e-e798-4ec7-a87e-0a57a2cbafa7` and
`37eb51da-c2ed-4a04-853b-fdb10ec486b1` accepted packet
`41a8b737b53247fcc7ccdbcf6e5cb23eacf12fd414798d80f0e01b64d3b2483b`
without findings. Materialization then failed on the 48,000-byte wire limit.
The repair allows 131,072 wire bytes only for accepted-method handoffs, retaining
the 524,288-byte expansion bound, ordinary evidence bounds, integrity checks and
file-backed model context. API and worker validators agree. The live retained
packet passed offline lossless transport replay at 79,669 wire / 405,609 expanded
bytes; that replay used no authority and created no task. The expanded regression
suite passed 187 tests. Deployment and actual engineering completion remain
separate evidence requirements.

Do not infer end-to-end autonomy from method acceptance: operator-prepared
successors, coverage-package recovery and transport repairs were still needed.

## Engineering commissioning and bounded recovery (2026-11-23)

After deployment, task `ea2a7ea4-dd89-441a-b567-57d0f12b87cb` entered its
separately approved engineering episode. An automatic same-session repair fixed
the focused-test filename; nine focused tests passed. Independent code review
then rejected missing causal-input checks, a stub calibration terminal path,
insufficient native-runner integration and insufficient unmocked scientific
tests. Passing focused tests is not independent acceptance or completion.

Releases `43c4782` and `55a7304` route unrefuted reviews without executable
checks back to bounded author repair, and permit explicitly requested recovery
bound to the exact retained checkpoint. Recovery preserves the old terminal
state, model-call charges and original deadline. It cannot reset the episode
budget or bypass independent review.

The campaign was resumed through its audited API after task reapproval. An
unstarted lease had already encountered an authority conflict; its worker
abandoned the lease without releasing it. The worker now attempts authenticated
release on start conflicts. Expired or invalid leases remain fenced; an owned,
unstarted lease is released using the existing API and does not consume an
execution attempt. Regression tests cover both cases. This does not reclaim an
already abandoned lease or grant additional authority.

At this checkpoint, bounded recovery still requires a live retry after lease
expiry. No independent code approval, full validation, real-data calibration,
market-data backtest or BT-009 outcome has been demonstrated by this episode.
