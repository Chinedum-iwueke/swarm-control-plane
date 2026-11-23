# AEP-007: scheduling, authority and visible recovery

Status: **in progress; commissioning is not complete**. AEP-005/AEP-006 are not
the production default. Controlled fixtures are not genuine-candidate receipts.

## November 23: retained-evidence audit and V2 assurance

### Latest handoff status

The founder activated `1c7609b0-a62c-4917-bbf3-503f672aabb2`, digest
`8c5b60d71d408a611e3b6e676c124deda2b82d020fe59198c4665f5c27a7aa42`,
under mandate `41abb4b9-84ff-4050-a6eb-b332f03ccccd`. Current-source coverage
and native planning succeeded; the refreshed method also published successfully.
The API deployment through `6b86fbc` is healthy. The handoff transport preserves
the full accepted-method file when its inline prompt exceeds the prompt limit.

Fresh specification review `e5f0886a-40a0-4ba2-9359-e14f2caaaef8` rejected
the retained solver-capacity and precision limitations. The causality reviewer
`2334a294-548c-466c-845e-48a710f180f6` returned an acceptance with explanations
appended to all 13 requirement keys, so exact-key validation rejected publication.
Its artifact is retained, not a published acceptance. The output schema now
constrains method check entries to the frozen requirement keys and exact count;
the independent runtime uniqueness/completeness validator remains unchanged.
This format repair cannot overturn the specification rejection. No engineering,
calibration or market-data backtest has started for this handoff. The current
campaign authorizes no further method correction or dispute adjudication.

The founder subsequently approved mandate
`ced6e5ef-b332-402c-b50d-bf025bc6654d` and activated method-only successor
`14866b1e-72ea-47a6-a20b-d7c6c4824634` (digest
`ce66f6d14a2b306290a103e6b3ec670d786e038a6b8e0d3d61e99b9b44578d70`).
It permits three author corrections, six diagnostics and one independent
adjudication per lineage until November 23 at 21:35 UTC. It cannot authorize
engineering, calibration execution, backtests or promotion.
Task `a68ae064-c75d-4476-b7c4-3b35bec29217` published a corrected method after
one author call and two diagnostics. Causality review
`3fcf262b-f6de-4003-ac9d-e11b96497639` accepted it with a valid exact-key output.
Specification review `07907c0b-915b-4339-8b43-35c0b5e6278f` rejected an omitted
12 outer-history generations: 65,548 required versus the unchanged 65,536 cap.
The controller automatically routed adjudication
`bd26536a-40d6-4fd4-b21f-cb1ebbd86873`; acceptance and correction remain unproved
at this checkpoint. The old handoff is not retrospectively certified.

Adjudication completed with `repair`, substantiating the twelve omitted outer
histories. Automatic correction then deferred as `context_requires_compaction`:
the receipt duplicated its prior packet and the catalog exceeded 16 entries.
Repair `eb52f8f` retains a hash-bound immutable-parent packet reference and packs
historical commissioning archives without removing scientific evidence. Exact
live-evidence replay validates the successor at 258,477 bytes; 117 focused
backend tests passed. The API deployment is healthy. The founder approved R2
`f48cd108-2c8b-48f8-a85d-74c51b71e0dd`, digest
`179e09d9d8478438ea2c1743a1f23cb09752f99fdd45a5345f29e9abed63b458`.
R2 retains only two unspent author calls, four diagnostics and the original
21:35 UTC deadline, with no repeat adjudication. This is an operator-assisted
transport recovery; uninterrupted end-to-end autonomy remains unproved.

R2 task `2387c92d-4631-4fda-b374-eb19a37e77e2` corrected the history accounting
with one author call and two diagnostics. Specification review accepted;
causality review rejected an implicit generation cycle and an undefined final
Newton iterate. Its automatic successor again exceeded the input envelope.
Repair `be6cf89` aligns API/worker aggregate inputs at 512 KiB/64 documents,
retains 256 KiB individual-document and existing prompt limits, and sends native
design diagnostics the transitive referenced evidence subset. Validation:
113 backend and 114 worker tests, plus a real source-bound native diagnostic.

The founder activated R3 `a6faf166-04d1-47fa-99fc-b8ab5fd1efff`, digest
`9063efdcaf3dfb70cd78dcbeec88430369088d38c00bca40a6a08deaefcca409`, using
only the final unspent author call and two diagnostics with the same deadline.
Task `2a91240b-19b5-45ec-b4c8-1a7c364e10b5` published a ready packet, but API
custody still expected the complete diagnostic catalog. Repair `d404a47`
reconstructs the exact projected catalog before verification, also preserving
legacy full-catalog receipts. The unchanged real result verified in a read-only
replay with one model call/two diagnostics; 114 backend tests passed. This
consumer omission required operator repair and must not be counted as autonomous
completion. Fresh independent review and engineering remain outstanding.

### R3 terminal review and precision constraint

R3 specification review `11640223-9621-4a04-b38c-6a0d6732efe8` accepted;
causality review `72022000-4c48-4f62-bf60-22c302818837` rejected the remaining
calibration precision procedure. The campaign closed as `completed_no_candidate`
with zero trials and `native_recheck_budget_exhausted`; its last authorized
author call and two diagnostics remain charged. Neither review nor this closeout
is evidence of engineering or a backtest.

A read-only SciPy beta-quantile calculation at the approved native environment
quantified the frozen procedure's conflict. For each binomial count `k` among
`n` independent outer draws, use the exact two-sided 95% Clopper-Pearson interval:
`lower = beta.ppf(.025, k, n-k+1)` (zero for `k=0`) and
`upper = beta.ppf(.975, k+1, n-k)` (one for `k=n`). Requiring
`max_k((upper-lower)/2) <= .10` first holds at `n=104`:
worst half-width 0.0996610746; at 103 it is 0.1001499913.
At three draws the worst half-width is 0.4486484586.

The retained schedule costs `4*2*4*2*4*10000 = 2,560,000` statistic evaluations
per outer draw across all scenarios. Thus 104 draws require 266,240,000 such
evaluations, whereas the 8,000,000 cap permits only three draws. This is a
prospective pointwise interval/work calculation, not a power guarantee,
simultaneous-coverage result, observed calibration or claim that every alternative
uncertainty procedure is impossible. It assumes the required independent valid
draws are available; support failures cannot improve the count.

The next design decision requires fresh explicit scope: separately review a
calibration-budget redesign with resource bounds, or retain the cap and justify
an alternative uncertainty procedure. Do not rerun the unchanged incompatible
procedure or silently weaken the experimental requirements. No revised budget
or calibration execution is authorized by this calculation.

The [retained-evidence audit](aep-007c-retained-evidence-audit.md) found genuine
definition and workload-accounting defects, not missing reviewer transport.
Both review tasks received the same packet and its 18 evidence documents. The
latest campaign remains closed without engineering or backtests.

Bulletproof source `e092458` introduces `design-adequacy-contract-v2`: explicit
inline or content-addressed definitions, dependency closure/cycle checks and a
dimensioned workload ledger. Matching API/worker changes freeze output obligations
and approved caps, retain referenced evidence during recovery compaction, and
defer capacity-only findings without an author call. This is structural assurance,
not semantic/scientific proof or actual runtime cost measurement.

Validation before rollout: all 231 native governance tests, 105 worker tests,
65 focused backend tests, and four explicit cross-repository replay tests passed.
The latter include a real clean-source diagnostic subprocess at `e092458`, strict
author-output schema validation, synthetic repair/publication/API replay, and
capacity deferral without model calls. No genuine author or reviewer was invoked.
That test suite made no genuine author or reviewer calls. Subsequently,
control-plane `29938b8` was pushed and deployed; the API is healthy at migration
`d0a2b5f83c71`. BTC admission was freshly produced at `e092458` with unchanged
dataset bytes and receipt `a2ff837443e0b4d6dc998941394189465e634f638824284d75dd6de635a439e4`.

At 18:31 UTC on November 23, separate founder approvals authorized mandate
`b77dffd1-69bd-4c6e-9e0a-cbdc4a21ab2b` (digest
`3a98686584ad5a6a1e0975636e90688fafbe9e35217935f145962d3f6bdb9461`)
and campaign `5a9d3403-c058-4455-84b9-8d2746daf1b7` (digest
`df585fd5b83b14ef3bd4152e30a6c2d42405407f8e0ef4650247c4319c04f107`).
This is method-only authority: two author corrections, four diagnostics and
fresh reviews, with a method deadline of 20:29 UTC. No engineering, calibration
execution, market-data backtests, orders or promotion are authorized.
The deterministic draft succeeded. Method task
`e4c14e74-1949-46f2-9008-3e9441e19303` started its first attempt; no scientific
acceptance or engineering completion is inferred from that start.
The first live author correction then reached native recheck. It produced three
structural findings (two unresolved definition references and one invalid
primitive/dependency declaration). The episode automatically used its second
authorized author call without operator edits to the method, then passed native
structural validation after three diagnostics. Publication failed because the
summary duplicated its current proposal and exceeded 256 KiB. The completed
checkpoint remains intact. A lossless proposal-reference transport repair reduces
the actual retained summary to 250,770 bytes while preserving its original review
packet digest. Repair `44d930c` was deployed and checkpoint republication succeeded
on attempt 2 with the same two model calls and three diagnostics; API verification
reconstructed the exact retained state. A subsequent reviewer handoff also
duplicated the proposal as a card and exceeded its bound. Repair `ec11bc1` keeps
the canonical proposal in the packet and replaces only the duplicate card with
an explicit digest/location reference for large packets (65 API tests passed).
That repair is deployed; reconciliation advanced to independent method review.
Review tasks `722bf6a5-0395-45f9-9c0a-fd96172b3085` (causality) and
`f0a3918d-dd3a-4726-841e-8af40ed97b1f` (specification) both rejected the retained
packet: incompatible primitive/derived variable definitions and omitted solver
work remain. Causality publication exceeded the generic 16 KiB summary ceiling;
`97cd059` aligns the bounded review envelope and permits verified same-task
artifact replay. Recovery succeeded with zero model calls. Scientific rejection
is preserved; independent acceptance and engineering are not demonstrated.

Fresh exact-digest approvals commissioned mandate
`c87c2a79-ad1b-49ce-a9b9-6c49d5e25f1c` and campaign
`51daa205-4083-4a71-8081-34e12e0f6484`. Task
`bc71c743-2c17-4350-b4a9-7ad5b256b419` ran with both rejection receipts,
three author calls and six diagnostics available across bounded review-driven
correction. Method authority ends at 20:52 UTC November 23. Scientific identity,
experiment, minima and resource caps remain unchanged; no engineering or
execution is authorized.

At 19:02 UTC, that task succeeded on attempt 2 with one author call, two
diagnostics and one repair, after a publication-only recovery. The completed
checkpoint initially exceeded the 256 KiB aggregate review/result bound.
Transport repair `b40f0cd` retains individual document limits, bounds aggregate
method evidence at 512 KiB, and uses a hash-verified, lossless compressed envelope
only when the result exceeds the 256 KiB wire budget. Decompression has an
explicit output bound and rejects corruption, trailing input and binding changes.
The actual result is 282,016 bytes expanded (JSON with spaces), 86,567 bytes on
the wire; API replay verified the exact audit state and review packet. Recovery
made zero additional author/diagnostic calls. The campaign advanced to fresh
independent method review, not scientific acceptance or engineering. Validation:
64 worker and 83 backend tests passed; deployed API health is healthy.

At 19:05 UTC, both review tasks completed successfully as executions, but their
verdicts differed: one accepted the pre-authoring definition; the other rejected
the conflicting latent and derived meanings of `g_t`. The controller recorded
`method_correction_created` and automatically started successor
`f28e6be3-1707-4dd8-9136-030c46bd2660`, preserving the original deadline and only
the remaining two author calls/four diagnostics. No operator edited the proposal
or created that successor. This demonstrates bounded review-to-correction
recovery, not completed method acceptance or engineering. Solver-capacity and
Monte Carlo-precision limitations remain explicit.

The automatic successor subsequently completed and published without operator
recovery. Both fresh review tasks (`30bfeb61-7be6-4a3e-8272-9666e80f16d2` and
`2f2af80f-a783-4f11-823b-95d57c8ae33a`) accepted packet
`a91a4325bae0d05a8cfcf4902a0537c045498947dde15bc486ae6b91de515cc7`.
Total usage across the two tasks: two author calls, four diagnostics and two
repairs. The correction uniquely names the latent wick driver and derived range
control. This is pre-authoring method acceptance with retained solver-capacity
and precision limitations, not calibration success or scientific qualification.
The campaign reached `materialize_accepted_method_handoff`.

The founder approved mandate `41abb4b9-84ff-4050-a6eb-b332f03ccccd`, digest
`68382243f1f1695b0ba15cdf2353bc5097249b809829d1c087675f777d696c42`, for
current-source native plan revalidation, fresh review handoff and separately
approved engineering/synthetic tests. Campaign activation and engineering task
approval remain separate. No market-data backtests or real-data calibration are
authorized; discovery remains disabled.

Broad discovery is contained by a stopped discovery director and agent-level
pauses on intelligence, senior research, representation and strategy engineering.
The workflow drain was lifted only for this isolated commissioning queue.
An unstarted discovery allocation `A4-b77dffd1-001-I` was cancelled through the
audited cancellation service with zero attempts; historical counters remain
charged. Repair `394cb95` adds immutable `discovery_enabled` permission (legacy
default true), checked by idea execution intake, direct cycle creation and
reconciliation. The fresh successor explicitly sets it false. Live reconciliation
returned active with zero cycles; 148 discovery tests passed. Existing approved
mandates are not rewritten. This disables discovery only; it does not grant or
replace campaign, engineering or execution authority.

## AEP-007C: engineering handoff commissioning

November 18: mandate `93d63bf8-8590-472c-849f-83cdf4d92d1b` and campaign
`0e1a11a4-92da-4c6e-ad2a-70ecc9249789` were separately approved. Campaign digest:
`cb91a7842496162a5b47340eaebb83a5cff4ad35170ca3171e487dd5df1af6cb`.
Drafting and the single authorized diagnostic refresh succeeded. Method task
`838b8a3a-a805-4949-9de9-f0462db97e4a` published packet
`cd29071a20da3b641d5d7247281a3240e47a1d61a12fdef3e1834f3224f736d2`.

Fresh route `9acbfab7-1c00-430a-8c77-0f1052ceb7fc` split: causality approved;
specification rejected the unspecified induced-estimand coefficient solve.
The rejection requests an exact functional, numerical approximation, solver,
convergence/rank checks and verification tolerances. Earlier acceptance remains
historical evidence, not permission to ignore this new finding. The campaign
closed `completed_no_candidate` with zero trials after
`native_recheck_budget_exhausted`. No engineering task was materialized.

Local follow-up changes classify this exhaustion as `await_authority_or_capacity`
rather than an unknown requirements conflict, without enabling automatic repair.
Correction guidance now requires reproducible solver definitions, separate
verification, compute accounting and explicit failure behavior for any such
method, not only BTC. These changes are not yet deployed.

Replacement mandate `248dd01b-6b67-42a8-83e1-1ba258e992a7`, digest
`b1b773c7b508d67932909fde28ec7c81a55cba791a7fe96d9e870480a4b90589`,
was explicitly approved and activated. It retains the original
13:31 UTC expiry and source; correction campaign activation and engineering
approval remain separate. No scientific calibration, market-data execution,
orders or promotion is authorized. The three-outer-draw precision limitation
remains unresolved.

### Correction campaign preparation failure and local repair

The founder separately activated campaign `fd78f596-39f3-4509-a401-3a371d804acd`,
digest `b9834d48697839e743ce3d015352bb0a6bb478f742b3ce5288497af1db88f9eb`.
Task `bd53dc47-88a5-4427-b466-f050cc53ef60` published a blocked method outcome:
`invalid_stage_result` at `propose`. Task-level `succeeded` means publication
succeeded, not scientific correction. One author reservation and one diagnostic
were recorded; no model output directory was produced. Do not refund historical
reservations or infer paid inference solely from that counter.

An offline replay of the exact retained context reproduced the cause: 154,319
bytes exceeded the 128,000-byte prompt bound even after lossless subtree
deduplication. The local adapter repair permits a `method-correction-file-v1`
fallback only for this specific post-deduplication size error. Raw input bounds,
reserved-reference checks and all original requirements remain enforced. The
full canonical evidence is exclusively created as a read-only artifact with an
exact digest and byte count; the prompt instructs read-only inspection of that
file. Its integrity is checked again before accepting the model output.

The real-context replay produced a 446-byte index retaining all 154,319 evidence
bytes, verified the digest, and made zero model calls. Worker regression tests
cover ordinary inline/DAG contexts, complete file-backed evidence, tampering,
raw overflows and reserved references. This establishes transport correctness,
not that a model read every obligation or produced a valid scientific correction.
The repair is local and not yet deployed; no historical task was restarted.

### Deployed transport retry and output-bound mismatch

Transport repair `d168d0a` was pushed to main and deployed to the API and method
worker. The founder separately activated successor
`f7d2093e-dd92-4018-94bc-435e1a5d1843`, digest
`9289a643494b1b6cd21296ff6c6b9c1db441a0716f0f7549389c2b4f3fa35222`,
using only the original remaining one author reservation and three diagnostics.
Task `2e043061-0bfa-4008-8ab1-5c106fc38fae` passed the file-backed handoff,
produced a correction and ran native shape validation. It then deferred with
`repair_or_model_budget_exhausted`: `dependence_assumptions` contained 4,015
characters, exceeding the native 4,000-character bound. No fresh independent
review or engineering task followed. This is observed transport recovery, not
method acceptance or engineering completion.

The next local repair aligns the author output schema and prompt with the
native statement bounds (1..4,000 characters) and structured calibration rule
bounds (20..4,000). It does not truncate evidence, change native limits, repair
the historical proposal in place, or reset counters. Boundary regression tests
compare statement schema limits with native shape checks; 52 worker tests pass.
This output-schema repair is not yet deployed. Additional authoring requires
explicit bounded authority; calibration precision remains unqualified.

### Diagnostic envelope boundary repair

Output-schema repair `da552d6` was pushed and deployed. The founder approved
mandate `76ec4c00-f8c8-4ace-8eef-ca33713ea6bf` and activated campaign
`621a8fa9-8350-4b6d-92ed-336898ee6587`, digest
`76777f7005d269b3adba349b08a00ab5e4fd8501a63dfec773ba9a03068fc1cb`.
Its task `d56c0830-889f-4236-9bfe-bee2fcf9e6fa` blocked during deterministic
diagnosis with zero model calls: the approved 16-entry catalog plus a generated
preflight receipt exceeded the diagnostic result's separate 16-entry limit.

The local fix permits 17 entries in `Diagnosis.evidence`: 16 approved input
documents plus one generated receipt. `MethodTaskContract.evidence_catalog`
remains limited to 16; this does not expand scientific input authority or alter
byte bounds, digest verification, findings custody, budgets or approval gates.
The exact retained 17-entry diagnostic now validates offline with all hashes
verified and no checkpoint modifications. Its disposition remains `repair`,
not acceptance. Tests cover full catalogs on native-readiness and preflight
paths, free duplicate replay, input-catalog overflow and 18-entry result
rejection. All 55 focused worker tests pass. This envelope repair is local,
not deployed; the historical blocked task has not been restarted.

### Envelope retry reached independent review

Envelope repair `8461d97` was pushed and deployed. The founder activated
campaign `4b948c0e-0642-407b-ad3d-6297ef85079f` under mandate
`9c45a916-fa1c-46af-9637-c290a25b3f43`. Its task
`53e92e3c-37e7-45a4-a7c8-d5bdbbbf0283` completed one author correction and
two diagnostics, reaching independent review with no native findings.
Packet `bcc275e2a1fd0da238fa1c5cffa6faf52b52d0cef5eacb42d780e918f7ce6cf9`
was reviewed on route `a2d6bac2-a5aa-40b8-abc9-50eaabadd790`.

Causality approved; specification rejected an optimized `theta_0` with no
defined role in the retained generative equation. This is a genuine unresolved
method-specification finding despite native structural readiness. The campaign
closed without an engineering task or backtest. Local correction guidance now
requires whole-method parameter/equation/dimension reconciliation and solver
cost accounting; it is not a new deterministic mathematical verifier.
All 55 focused worker tests pass. This guidance is not yet deployed.

Mandate `489a42e8-0187-47ec-8654-466d618c9f23`, digest
`9c1906acd425d11ab4103bb0aa71fd0f84bf72d2cad512dfe87128fefa7fa13c`,
is prepared and awaiting approval for one additional correction and two
diagnostics, retaining the original 13:31 UTC mandate expiry. Campaign
activation and engineering approval remain separate. Historical evidence and
counters remain unchanged; no calibration or market-data execution is authorized.

## AEP-007B: bounded calibration and window correction

November 18 commissioning is **complete in bounded method-correction scope**.
Both independent reviewers accepted R2; engineering and execution remain gated.
The founder approved
mandate `98799db695cc75014b938bef861df864c1a0c135c62ba640d02a6d95abbc6983`
and campaign `8c98415f3d990bc28990cc72cb9309535fe5dcf81dcf6fdb293b6b87503773cc`
(`5d1bba1e-f4af-4a97-8b04-4955d9729ea9`). The latter permits two author
corrections and four diagnostics until 07:03 UTC, then fresh independent reviews.
It grants no engineering, calibration execution, backtest, order or promotion
authority. Prior proposals, reviews and counters remain immutable.

`method_window_binding.prepare_window_binding` prepares explicit successor
evidence from custody-verified native plans; it is not an execution authorization
or an automatic campaign activator. It checks source/digests, coverage references,
research-clock alignment, envelope, partition capacity, warmup, split gaps and
target-only tail. It preserves the parent proposal and records separate calendar
capacities and unobserved eligible support. The approved successor uses the native
scientific year beginning May 18, 2025, not the historical card's August dates.
Historical card evidence remains available; only its dates are superseded.

The correction adapter now receives explicit review requirements as well as
findings and evidence. Oversized contexts use lossless subtree references within
the approved context budget, without summarizing or dropping obligations. A
prospective real-context probe retained all seven findings: 140,839 bytes became
113,793 bytes before episode bookkeeping, within the 128,000-byte bound.
Calibration guidance requires complete joint laws, shared outcomes, induced
estimands, work-unit accounting and prospective precision criteria, rather than
asserting unexecuted calibration is qualified.

Focused validation: 52 worker and 55 backend tests passed. This is infrastructure
evidence only; the observed correction and reviews needed for closure are recorded
in the closeout below.

### First correction and remaining allowance

Release `ae67239` is on main and deployed to the API and campaign director; the
VM1 method worker uses the same checkout. Task
`cb0d46a1-36d8-4f93-ad6a-c7d116ac23cf` completed one author correction and two
diagnostics. Audit reconstruction now distinguishes the bounded transport from
expanded history, whose repeated catalog snapshots are bounded by the approved
tool-call count. The exact retained result verified without another author call.

Both fresh reviewers rejected. One found the DGP's exogenous controls/events did
not implement the registered causal OHLCV feature construction. The other cited
old primary dates as current support-minima text; that text is absent from the
current proposal's rationale, so historical versus current evidence needs explicit
resolution, not automatic acceptance of the assertion.

Automatic correction then deferred with `context_requires_compaction`: adding
review lineage exceeded the native 16-entry catalog limit. Campaign history is
closed and unchanged. `compact_historical_catalog` packs only historical
commissioning metadata, preserving original document hashes and protecting
dependency/justification references; it does not drop scientific evidence or
increase the native limit. Thirteen recovery tests pass.

R2 `0e11b4ba-541f-49ce-9aa4-8b7c6c1b2627`, digest
`7d6a9c8e0b722d2b8140115fa99c4ba5048e66c7aa422063155623f704e3b4b1`,
received separate founder activation. It carries only the original unspent one author
call/two diagnostics and the original 07:03 UTC deadline. Its 14-entry catalog
and 123,380-byte lossless prospective context passed preflight. Preflight alone
was not method acceptance or permission to execute calibration.

### Observed AEP-007B closeout

R2 task `527b6835-2a6f-486b-8006-ee86082c74d2` completed its correction and
diagnostics. Both assignments on route `e36dbf24-9d1a-4b21-8845-6c09ef09ea20`
completed with **approve** and no blockers:

- Strategy specification: `238ac75b0a8806d07c72fa20f12c5096ef8f3a53cfd4757e86f114e6f0d1830d`.
- Causality/leakage: `7a4108b1fb649190b03db484a5244389f27978057d3415cd00158e01c0f15188`.
- Accepted packet: `6108291de24f4b8dbb18dcba0095b0db40210ce98b42a66173918fcfa4a7ae53`.
- Verified result: `ba0afd6d5bd5e68d44968214309cfaabd97b798e92551197c158e788e07965cb`.

The correction derives registered features and the common target from a shared
OHLCV history and adopts the approved native windows. Across the original and R2
campaigns, two author calls and four diagnostic steps were used; no old counters
were reset. The controller now reports `materialize_accepted_method_handoff`.

This is acceptance of a prospective method specification, not successful
calibration: the declared three outer draws remain insufficient for the stated
Monte Carlo precision criterion. No calibration was executed or qualified, and
no engineering/backtest authority was granted. AEP-007C must preserve this
limitation when binding implementation work; scientific execution cannot treat
this review as evidence of attained precision or power.

General transport, explicit-authority and catalog repairs required operator
deployment and separately approved successor activation. This does not certify
unattended recovery or the complete research-to-BT-009 loop. Code is on main at
`ae124d9`, deployed to the API/director and VM1 method worker; 68 backend and 52
worker focused tests pass. Broad discovery remained stopped.

## AEP-007A: evidence-access handoff (local implementation)

Large method/design-adjudication packets retain the existing 262,144-byte raw
contract ceiling. Inline and lossless-DAG contexts remain unchanged. When DAG
deduplication cannot meet the 100,000-byte prompt limit, matching API/worker
`review_context` implementations produce a `review-context-file-v1` index.
This requires a real method packet with digest-valid evidence and at most 64
criteria. It does not admit arbitrary oversized legacy reviews.

The worker retains the complete canonical contract in task-local
`artifacts/review-evidence.json`, makes it read-only, and checks its exact digest
and length before inference and before accepting output. Repeated preparation
reuses only identical evidence; missing, substituted or symlinked evidence fails
closed. The reviewer is instructed to read bounded JSON sections, compare the
method and native plans, and report every criterion's retained evidence digests.
Missing coverage or unknown digests cannot yield a successful worker result.
The index and coverage are retained in the execution summary; full evidence and
the raw verdict are artifacts. Canonical verdict serialization is unchanged.

Coverage is a reviewer assertion, not a filesystem access audit or proof of
scientific correctness. The two independent reviews and exact requirement checks
remain mandatory. Tests cover transport, admission, restart preparation,
missing/tampered evidence, coverage rejection and mocked accept/reject outcomes.
They preserve cross-section contradictions; they do not demonstrate that an LLM
will detect every contradiction. **Deployment and a genuine candidate review
outcome remain required for AEP-007A operational closure.** No new mandate,
engineering execution or backtest is authorized by this change.

### Rollout verification, November 18, 2026

`d8353d8` was pushed to main and deployed to the VM2 API; both VM1 independent
reviewer services were restarted. The API reports healthy and `/health` returns
200. Focused validation: 32 worker tests and 12 backend tests passed (12 worker
parameter combinations intentionally skipped because they do not use file
transport).

A read-only probe joined retained method task
`2eb5b85a-9f1f-4aef-ad21-85d57bc8534c` with custody-verified native plans from
`da3c4409-b48c-44d4-b5f8-e3c70f8f645d`. The 158,539-byte evidence contract produced
a 2,837-byte file index, retaining six criteria and 14 evidence objects. This
was a transport probe, not a new review or an authorized successor. Zero model
calls were made. The existing commissioning mandate expired at 04:03:24 UTC;
a fresh exact-digest mandate and correctly bound successor remain necessary
before the genuine review outcome required for operational closure.

### Genuine review commissioning, November 18, 2026

The founder approved mandate `62e9d4e9-fe97-4733-a6b5-967a49d2101a` and exact
review-only successor `9b4a28a2-3999-41c9-973c-ddcaa7aa2162`. The successor retains
the BTC method, adds native plans and a seventh cross-plan consistency criterion,
permits one diagnostic and zero author corrections, and denies engineering and
backtests. Method authority ends at 06:26:23 UTC; mandate authority ends at
12:24:37 UTC. These timestamps are historical authority, not reusable permission.

Method task `c777fd16-72fc-461d-b14c-8ea61519765c` reached readiness with zero model
calls and one diagnostic. Result publication initially exceeded 256 KiB because
state and packet duplicated evidence. `ce6b3ce` adds exact packet reconstruction
from state evidence references; retained-packet parity reduced the summary from
268,074 to 169,445 bytes. The same checkpoint was operator-resumed without another
diagnostic. `ebdd615` distinguishes current diagnostics by source, request and
catalog bindings from historical receipts for the same proposal. Missing or
ambiguous current receipts still fail closed. Both repairs are deployed.

Strategy-spec review `42a82c25-d587-48b3-a3b6-c8f00fe5289f` succeeded operationally
and **rejected** scientifically. Its seven criteria have retained evidence coverage.
Findings identify an under-specified calibration law and inconsistent method/native
plan dates. This is a genuine file-backed review outcome, not scientific acceptance.
Causality review `3cf6beaf-8966-438b-a5c7-d1c503864a24` failed publication because
its outer blockers omitted one of its five detailed findings; the raw result is
retained. It has not been registered as an accepted or rejected review.

The bounded evidence-access path is genuinely exercised, but complete two-review
publication and broader autonomous commissioning remain open. Next: lossless
recovery of the retained causality verdict, followed by authorized correction or
adjudication of scientific findings. No fresh model call should be needed merely
to repair redundant blocker serialization. Combined regression checks: 89 passed,
12 inapplicable combinations skipped. Operator interventions remain part of this
record and must not be counted as autonomous recovery.

### AEP-007A closure: bounded handoff proof

Both assignments on route `8b39bb9d-c155-4bc6-ba7b-583489e3dad5` are now completed.
The strategy-spec receipt digest is
`afad54743cd27e986a013e46ec771718f5ce2092f0fff438a704814ca9e0ca74`;
the causality receipt digest is
`761d343467e1282624de045eeac472234e34e9febd4de6adea0da92e82f4765e`.
Both verdicts reject. Campaign `9b4a28a2-3999-41c9-973c-ddcaa7aa2162` is
`completed_no_candidate`, awaiting founder closeout. AEP-007A is complete only
for its evidence-access/review-outcome scope, not scientific acceptance or
autonomous engineering certification.

`47a5917` adds monotonic completion of redundant rejection summaries: every
existing blocker must exactly match a detailed finding; no finding is dropped,
reworded or converted into acceptance. Unknown blockers fail closed. Explicit
same-task recovery verifies the retained artifact digest, complete contract,
source, evaluator, workspace metadata, evidence coverage and current lease.
Raw output is preserved separately from the projected canonical verdict.

The first recovery attempt incorrectly read `failure` instead of lease-carried
`prior_failure`; it entered ordinary review and was stopped. This additional
interrupted model attempt must not be hidden or counted as free recovery.
`b3f58dc` fixes that handoff and tests it. The final publication-only attempt used
zero model calls and retained all five causality findings. Recovery was explicitly
operator-assisted. The method episode still used zero author calls and one native
diagnostic; no engineering, calibration execution or backtest was run.

Next is AEP-007B: assess the retained scientific findings and prepare an explicitly
authorized correction/successor. The zero-correction commissioning campaign does
not authorize that work. The handoff proof does not make either reviewer infallible.

## Deployed baseline

`200e09f` deployed source-bound method publication. `6631a6d` added separately
assigned method reviews, accepted-method engineering materialization and the
Mission Control bounded-episode inspector. VM2 API and both directors were
verified healthy on the same image. The two VM1 independent reviewers were
restarted; the Mac serves the inspector. This did not resume autonomous work or
register a method designer.

## Authority and scheduling

New campaigns can include exact `method_design_requests` keyed by candidate ID.
They are frozen into the campaign and require explicit founder activation during
commissioning. Existing approvals do not authorize this new lane. Materialization
uses the campaign lock and content-addressed task identity. Source, candidate,
mandate, deadline and frozen request are checked again during reconciliation,
task start and heartbeats. Historical specifications and mandate counters remain
unchanged.

The restricted method executor checks its lease before effects and periodically
during work. Model-call reservations require the configured billing lane's permit.
Deterministic diagnostics do not require a model permit. Drain pause prevents new
leases without cancelling already executing work. Provider recovery requires a
changed trusted circuit revision; unchanged delivery does not repeat model spend.
Interrupted reservations remain charged, with original budgets and deadlines.

## Review and engineering

An operationally succeeded method task is not scientific acceptance. Publication
verifies the task contract, unchanged scientific identity/support minima, repair
scope, budget counters, exact packet and native diagnostic receipt. Native design
readiness explicitly retains independent-review and calibration obligations.

Two separately leased AGT-006 reviewers receive the exact packet and obligations.
Evidence references, identities, active profiles/packages and producer exclusion
are checked before consuming fresh or cached reviews. Legacy review serialization
is unchanged. Each method-review task permits one attempt and one local call.

A frozen `method_engineering_requests` entry can bind an accepted packet to an
engineering episode. Both native smoke/scientific plans must be ready, included
in reviewed evidence, and backed by a successful source/candidate-bound planning
task. Dataset, representation and windows must match. Engineering approval remains
explicit during commissioning. Source merge/rebinding is a separate gate.

## Bounded review correction (local increment)

`alpha_method_recovery.py` creates an immutable successor after a concrete,
evidence-bound rejection. The successor retains scientific identity, support
minima, source, authority and remaining deadline. It subtracts already consumed
repair/model/tool/work budgets. A campaign lock and recorded successor event make
repeated delivery idempotent; altered lineage fails closed. Authority revocation
also blocks reuse of an existing successor.

The worker consumes retained rejection findings before another native diagnosis.
A changed proposal requires a new exact packet and fresh independent review.
It cannot convert a rejection into acceptance. Exhausted budgets, deadline or
bounded context produce a retained zero-trial deferral through the existing
candidate-deferral path; unchanged retry is forbidden and siblings can advance.
This is bounded correction. The separately authorized dispute lane below does
not waive either independent review.

## Independent dispute lane

New campaigns may explicitly freeze `method_dispute_policy=independent_once`.
After rejection, a third review-only evaluator receives the exact retained packet
and both reviews; the producer and both original reviewers are excluded. It must
bind each rejected finding to retained evidence and choose `repair`, `recheck`
or `disputed`. It cannot issue approval. This is interpretation/scope adjudication,
not an empirical counterexample or proof that a reviewer is scientifically wrong.

One adjudication is allowed per correction lineage, with one task attempt and one
model call. Expired episodes and exhausted native recheck budgets defer before
adjudication. A recheck preserves the method, refreshes native diagnostics and
requires two fresh reviews. Unresolved disputes defer; changed methods follow the
ordinary bounded repair path. The adjudicator is a separately registered profile
and context, not the author checking its own work.

Missing, unready or mismatched native planning evidence now produces
`method_dependency_deferred` before reviewer task creation. The retained blocker
names the planning task and `native_feasibility_planner` owner. Reconsideration
requires verified plans in a successor packet, fresh review and explicit successor
authority. It is not a retry of the same missing dependency or a waived gate.

## Method-designer provisioning

The local bootstrap supports `--package alpha-method-designer --method-model MODEL`.
The model is mandatory and recorded in both registration state and worker settings.
Its producer profile uses `provider=codex`, the actual configured model, a dedicated
context group and `alpha_method_producer`, not deterministic-native provenance or
reviewer capabilities. Identical registration is reused; changed model/profile or
runtime settings fail closed rather than silently changing provenance.

`worker/systemd/install-alpha-method-designer.sh` checks root-owned mode-0600
registration files and installs the dedicated service **without starting or
enabling it**. It refuses replacement of an active service. The service is non-root,
has a read-only primary checkout, scoped writable paths, one CPU and a 2 GiB memory
ceiling. It uses the existing authenticated Codex runtime; it does not copy keys,
install dependencies, enable hybrid authoring or initiate model calls.

Registration state and environment must be named
`/etc/invariance-swarm/alpha-method-designer-state.json` and
`/etc/invariance-swarm/alpha-method-designer.env`. Register only a released exact
control-plane commit using the existing operator procedure, then install the unit.
Activation remains separate and requires the exact approved commissioning campaign.
On 2026-11-17, the dedicated unit was installed but left inactive. Live producer
`7199afe8-a966-45c2-b7d3-51fde6ef373d` and adjudicator
`634608fa-3182-4b62-9a3f-70989e608daf` were registered against release `2112f09`,
using `gpt-5.6-sol` and distinct context groups. Adjudicator profile
`744c057f-e475-4c88-8b0c-29276226ffdd` has review-only authority.
Provisioning now persists credentials before sending an authenticated,
package-attested heartbeat and registering the producer profile. This does not
lease work or call a model; retries preserve identity after partial provisioning.

Release `2112f09` was deployed to the VM2 API and both directors, verified on image
`sha256:5ee9229940a01a8eac9099d55ad21fa1e382e7f015fc29adf388caf6e837d317`.
The API was healthy. Mission Control was installed/restarted on the Mac and
returned HTTP 200. No commissioning campaign was activated by this rollout.

## Visibility and verification

The task inspector renders current-attempt progress or retained results, owner,
stage, blocker, repair/model budgets, deadline and expandable evidence. Unknown
token usage stays explicit. Synthetic browser inspection verified desktop and
390px mobile rendering and evidence expansion; it was not a production API test.

Focused tests cover source/authority revocation, contract parity, immutable
publication, separate review routing, exact accepted-method handoff, correction
budget conservation, duplicate delivery, altered lineage, provider deferral,
worker repair/restart and zero-trial deferral. Most native/model calls in these
tests are stubbed. See the test files named for `alpha_method`, `method_review`,
`method_episode`, `engineering_episode`, `alpha_campaign` and provider capacity.
The prior follow-on runs passed 172 backend tests, 98 worker tests and one executable
JavaScript inspector test. Terminal results take precedence over older running
heartbeats; attempt, next action and recovery condition are explicit when recorded.
Three worker tests used the actual clean Bulletproof checkout and native CLI,
with synthetic contracts and scripted corrections. They verified missing-field
repair, native receipt custody and restart reuse, not paid-model reasoning or
market-data backtest success.

The provisioning/dependency increment additionally checks explicit model provenance,
configuration drift, inactive-by-default installation and native-dependency deferral
before review. The focused backend suite now has 175 passing tests. The
worker suite has 113 passes (including three actual native-CLI checks), and the
JavaScript renderer test passes. The unit passes `systemd-analyze verify`;
the host reports unrelated existing snapd
`RestartMode` and netplan unit-read warnings.

## Remaining acceptance boundary

- Retain rollout evidence and complete exact-digest commissioning authorization.
- Commission typed discovery inputs and dependency recovery under an explicitly
  approved exact campaign; do not infer requests from prose or migrate old work.
- Exercise the integrated scheduler with retained commissioning evidence,
  including restart, quota, unavailable data, exhausted authority and siblings.
- Commission the independent adjudication route on retained real evidence;
  synthetic routing tests alone do not establish scientific review quality.

The founder authorized preparing a commissioning proposal, not activating an
unspecified digest. The latest observed commissioning mandates were completed;
their budgets must not be reset. AEP-008's genuine-candidate engineering, smoke,
one-year BT-009, memory and replenishment certificate remains a separate milestone.

Read-only inspection on 2026-11-17 confirmed BTC campaign
`13a791af-9918-47c0-b924-07bfbf5ffb6c` is `completed_no_candidate` with its queue
exhausted. Its retained candidate is `bfefd78f-113e-4383-beeb-1ba964a8622d`, bound
to Bulletproof `ff945426f572d1a72b84714287fc34549b9290b0`. The current clean native
checkout is `4e98fab3c1073d8a5c83615ecbe2c0a428193b7c`. A commissioning successor
must explicitly bind its intended source and revalidate dependencies; copying old
planning receipts into a new source contract is not authorized or valid. No new
campaign was activated by this increment.

## Commissioning records (2026-11-17)

The bounded native admission command revalidated only the BTC panel with a 2 GiB
memory ceiling and one CPU. It finished successfully in 25.9 seconds. Registered
receipt `0a5c75b0-b17a-40f0-9a3c-4251b98383b2` binds native source `4e98fab` and
unchanged panel digest `9a211d8818c5ab8ec82ad5a7d38957e63eb387ea83d4b00541922a0eeca4aacb`.
This is data admission, not feature coverage, power or scientific acceptance.

- Mandate `5ab5a83d-aa24-4d7f-82c5-363172b2a54a`,
  `ALPHA004-AEP007-COMMISSIONING-20261117`, received exact approval of digest
  `078aecffa81580c3a1c10eeda238d39fca6c90a72b5a64fccf9230aa2dc1df19`.
  Limits: one cycle, two hypotheses, four total trials, one concurrent campaign.
  Expiry: 2026-11-19 16:54:57 UTC. No capital, orders, shadow or live promotion.
- Method-only campaign `e17260b6-2d51-4f21-95af-1b96a7d4b8d0` received exact activation
  of digest `a5eb727506c26ee77882fd2cf345edeefd9a795bb01eb7aae31e0fc977645291`.
  It retains the historical BTC candidate and original support minima, with two
  author calls/repairs, six diagnostics, a two-hour method episode and one
  interpretation adjudication per lineage. Missing prospective-design fields
  are explicit work for the designer, not manually invented scientific evidence.
  No engineering handoff request is present; this campaign cannot authorize
  engineering or native market-data trials. Those require separately reviewed
  source-bound planning evidence and an explicitly approved successor handoff.

The first campaign completed without a candidate after native field-shape,
publication-size and duplicate-context failures. Its two model reservations
resulted in one actual author invocation; history and counters remain intact.
Approved R2 (`b7ead273-5c1d-4fe1-aa39-7cb9b72ae4ad`) used one further author
invocation and safely deferred when justification cited a digest outside its
contract catalog. Neither campaign produced native scientific acceptance or trials.

Repairs `87be863`, `08d4303` and `9edfdc7` retain bounded evidence, remove duplicated
diagnostic envelopes and constrain correction fields and citation references in
the model output schema. Deterministic validation still checks the returned output.

R3 (`6b4e6231-96e8-4f99-9851-ac01b82a3a3d`) was explicitly approved and activated
at 17:20 UTC on November 17, with digest
`206d6709d12bf0898b89da83ab29f17a0619addc6690eb44f7754c4d385f7c58`.
It allows one additional author call and three diagnostics, preserves prior
counters and the original method deadline of 19:00:37 UTC, and requires fresh
independent review. The method designer and adjudicator units were started;
broad discovery remains stopped. No engineering, backtests, orders or promotion
are authorized. AEP-007 remains unqualified pending observed commissioning results.

### R3 observed review path

R3 reached native diagnostic readiness with one author call and two diagnostics.
Its first publication exceeded 256 KiB because the audit state and review packet
both repeated diagnostic catalog envelopes. Repair `4d28468` preserves the full
checkpoint while projecting each underlying evidence document once for review.
The retained result shrank from 312,936 to 220,436 bytes; the review packet is
62,980 bytes. Resuming task `1fe761d2-17df-42f5-9db0-6a3d8744b86f` published it
without another author call or diagnostic.

Packet `8b2fce05ed2726de8aff1dc36c98b2df6e21f0c6792699761447951e36a1a8d3`
was routed to both independent reviewers under route
`645a9a25-0370-41cd-a6e2-3cf2f1016a42`. Both rejected the missing reproducible DGP
definitions while preserving identity and support minima. The scheduler routed
a separate adjudication under `acff2562-040b-428b-afde-4d7a3d9d344b`.
The provider initially rejected an unsupported open-map output schema before
inference. Repair `4b3ae6e` compiles the exact finding keys and admissible evidence
references into a strict closed schema. The same adjudication task then completed
with decision `repair`, review digest
`e6bfedf275a4829f33d35695f8da4e8d182c360d9f31885887701debcde83442`.

Repair `b4bedc5` lets the shared evidence validator explicitly validate the
single-adjudicator lane; default scientific acceptance still requires both
original review kinds. Validation: 74 focused backend and 32 worker tests passed.
These observations prove diagnostic publication and genuine rejection/adjudication
routing, not scientific acceptance, a successful repair successor, engineering,
calibration execution or a backtest. Further authoring requires fresh bounded
authority because R3's single author call is spent.

After deployment, automatic reconciliation retained a deferred attempt
`23e2f4cf-66de-4b0d-9852-815da8291132` (digest
`88e14bd861e3412969d8f3e6b68643aa1ad267d123660c3d5c061681e6acd3bb`)
and closed R3 as `completed_no_candidate`, with zero trials. The dedicated method
designer and adjudicator were stopped after closeout; broad discovery was not
resumed. No old budget or scientific result was rewritten.

### R4 correction and transport validation

The founder approved R4 (`8c3a0f28-5ac1-4884-b927-3572330af65a`), exact digest
`95d9090ed2257683c045b52abbadec36ce6a90159585325465d65534a302947a`.
It retained both R3 reviews and adjudication and allowed one further author call,
three diagnostics and fresh reviews, with no repeat adjudication or execution.
The corrected method reached native diagnostic readiness with one author call
and two diagnostics. Publication again exceeded 256 KiB because catalog-bearing
audit envelopes still duplicated their children in transport.

Repair `80160ec` adds `method-task-result-v2`: audit envelopes travel as bounded
content-addressed references. The API verifies each reconstructed envelope digest
and the original complete audit-state digest before applying existing custody
checks. Local checkpoints remain unchanged. R4 transport decreased from 274,294
to 161,883 bytes with an exact state roundtrip. Tests cover invalid references,
modified envelopes, mismatched audit hashes and cycles (51 backend, eight worker
tests passed). After temporary sudo renewal, the API and worker were deployed
and task `52b7314d-c032-4cb7-93ab-bea0ede7e446` resumed publication without another
author or diagnostic call.

Published packet `6cbe1264a7e9aac9c4ed9d9aa9b3c71e283ae9abca67c97a4212540607a3965f`
reached fresh review route `4ff7aff9-6c44-4e15-8db2-06a807ac3c3b`. Both reviewers
rejected the proposed calibration: it lacked a joint four-variant construction
for the registered Holm families; fixed event counts did not distinguish the
registered quantiles or partition sizes; and the inner-replicate schedule
conflicted with the retained bootstrap procedure. These are prospective design
defects, not failed empirical results. Identity, minima and retained obligations
were accepted by both reviewers.

R4 automatically closed as `completed_no_candidate`, with zero trials. The method
designer was stopped after closeout. The transport/restart/review/deferral path
is observed; successful scientific correction and engineering remain unproved.
Further authoring requires fresh bounded authority, not reuse of the spent R4 call.
