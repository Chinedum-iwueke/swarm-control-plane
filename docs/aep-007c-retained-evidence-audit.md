# AEP-007C retained-evidence audit

## Status: repair required, not a transport retry

Read-only production inspection on 2026-11-23 verified the retained method result
and compared both independent review task inputs. No author, reviewer,
calibration or backtest was invoked. No production state was changed.

- Campaign: `629d723b-2321-4cf8-b192-cf83eb34815d`, `completed_no_candidate`.
- Method task: `a4c04d7a-5ae0-4287-91ed-fa06fc74eed9`, `succeeded`.
- Inner result: `ready_for_independent_review`, one model call, two diagnostics,
  one repair. This is publication success, not scientific acceptance.
- Review route: `1a4266d0-42fd-4c34-8c18-56bd789da9e0`.
- Exact packet: `9332371765ee23500cf98257e945f6c554b3c4164be8075d079f07ccf37de63c`.
- Both reviewer task packets equalled the reconstructed packet, including its
  18 evidence documents. `verified_method_result` checked result custody and
  expanded audit-envelope hashes before inspection.

The strategy-spec reviewer (`a4324ec7-f061-48c1-9a09-b76b357bb99d`) accepted;
the causality reviewer (`8938ebb5-d350-4ad0-90af-0adea89c6751`) rejected two
prospective specification defects. Neither verdict proves an experiment ran.
Equal supplied context does not prove equal model attention or correct judgment.

## Finding 1: primitive-to-feature definitions

Disposition: **substantiated specification inconsistency**.

The frozen estimator in evidence
`d7ceb3e4d211b234067e293b35fccdb441d7398d1db6ad8c67f02f52a60fb8f4`
defines absolute return from returns, prior volatility from history, range from
OHLC, and log volume from quote volume. Primary events depend on causal seasonal
surprise. These are derived features, not independently sampled inputs.

Historical correction
`ec1f3a38e343d09259bc819ae47ae4976642b67942d671241d7afb3e87ce7a53`
instead generates `S90,S180,R,A,V,G,E` as a seven-dimensional latent process,
labels `A,V,G` as those controls, and uses them in a return equation. It does not
provide an internally reconciled OHLCV construction making those labels equal
to the frozen feature calculations. Independently generated seasonal processes
also lack a construction from the registered quote-volume history.

Latest correction
`0371df17ad256d4c76b21f9d4c058176ac765799a023ac9142ffbdb0f17a59f3`
fixes the coefficient/intercept mapping but refers to a retained complete
derived-OHLCV law. Searching the expanded retained evidence did not locate a
definition resolving the contradiction. The defect is not evidence that the
transport dropped such a law.

Required successor evidence: an explicit chronological mapping from generated
primitives to OHLCV, then through the same feature/target construction used by
the experiment. Each feature needs one authoritative definition, initialization,
availability time and dependency path. Any alternative feature-level surrogate
must be explicitly justified as such; it cannot silently stand in for native
pipeline calibration. Independent scientific review remains necessary.

## Finding 2: work accounting

Disposition: **substantiated accounting omission**, with execution-stage limits
kept distinct from method adequacy.

The retained bootstrap ledger is:

`4 scenarios * 3 outer draws * 2 partitions * 4 variants * 2 statistics *
4 block-length analyses * 10000 replicates = 7,680,000 evaluations`.

The latest correction additionally specifies 65,536 solve/verification histories
and at most 320 full-functional evaluations. These are not the same unit as a
bootstrap statistic evaluation. It provides neither an aggregate conversion nor
a complete set of separately enforced resource caps. Reusing random innovations
does not make evaluation of the changed outcome and fitted estimator free.

There is also no explicit enforcement/accounting rule connecting the claimed
320 functional-evaluation cap to 19 starts, up to 500 iterations, finite-
difference Jacobians and independent verification. This audit does not assert
that all those maxima will be reached; it identifies the missing bound.

Native receipt
`27c81d3c4fc77ebc481f59b6c2306a0284f5475a936b3e8ce86397c53ac74fea`
reports 120,000 DGP/outer/inner units and explicitly leaves actual compute cost
unverified. Its structural pass cannot certify the larger workload ledger.

Required successor evidence: a typed work ledger covering generation, fitting,
solver/objective/Jacobian calls, verification and bootstrap evaluations. Either
use a justified common unit or distinct explicit caps with deterministic
reservation/exhaustion rules. Failure to fit capacity must defer execution;
it must not silently reduce scientific requirements. Three outer draws remain
insufficient for the retained Monte Carlo precision requirement.

## General recovery implications

1. Resolve inherited definitions by evidence digest and field path before review;
   prose such as "retain the complete law" is not a resolved dependency.
2. Check primitive/derived-feature ownership and chronological dependencies,
   while leaving scientific suitability to independent reviewers.
3. Validate a dimensioned workload ledger before paying reviewers to check it.
4. Acknowledge completed corrections without treating acceptance of one field
   as acceptance of every inherited definition.
5. Preserve historical proposals and both reviews. A new proposal needs fresh
   review; an operator audit cannot substitute for independent acceptance.

These are acceptance requirements for the next general repair, not claims that
new validators have been implemented. No automatic approval or re-review is
justified by this audit. The retained commissioning authority expired on
2026-11-18; machine sudo and task delegation do not renew it.

## Code references

- `backend/app/services/alpha_method_tasks.py::verified_method_result`: result,
  evidence-envelope and packet custody checks; not scientific correctness.
- `worker/src/swarm_worker/method_review.py::method_review_packet`: immutable
  proposal/evidence handoff.
- `worker/src/swarm_worker/executors/alpha_strategy_review.py`: method-scoped
  reviewer instructions and evidence-access coverage validation. The prompt
  distinguishes specification review from observed execution results.

Next implementation should enforce resolved definition dependencies and bounded
work accounting on general contracts, then use this retained candidate as a
regression case. A separately authorized correction must supply the scientific
definitions; this audit does not invent or approve them.
