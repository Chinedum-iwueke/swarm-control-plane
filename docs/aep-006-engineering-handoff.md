# AEP-006: accepted methods, author continuity and native handoff

Implemented locally on 2026-11-17. This opt-in extension does not materialize
production tasks, start backtests, grant execution authority or migrate old tasks.
Scheduling and current production registry checks remain AEP-007 work.

## Accepted-method boundary

`accepted_method_handoff.bind_accepted_method` binds an AEP-005 accepted packet to
an exact engineering contract. Its trusted materializer callback must verify current
AGT-006 review registration/custody; the local `review_complete` label alone is not
authority. A nonempty registration receipt is retained. The returned new contract
still needs the ordinary task authorization and lease path.

The handoff lives in the existing bounded `evidence_context` transport. It binds
the complete accepted proposal, requirements, evidence, reviewer identities and
verdicts, and the original contract basis (including allowed paths, tests, budgets
and source). Both source-bound native smoke and scientific plans must be ready and
present in the accepted evidence. It does not infer ready plans from arbitrary dates.
Oversized contracts fail transport bounds instead of dropping scientific clauses.

The existing engineering executor verifies this handoff before preparation or paid
authoring. The existing scaffolder, scope checks, dependency-complete validation
runner, independent code review and full-workflow validation remain in charge.
No general engine edit becomes allowed merely because the work concerns a hypothesis.

After a completed episode, `accepted-method-native-handoff.json` links:
- exact source and engineering contract;
- accepted method/review packet;
- reviewed code fingerprint and exact patch/bundle digests;
- same-code passing focused, independent review, validation and bundle receipts;
- separate smoke and scientific plan digests.

It carries false execution-authority and scientific-certification flags. It is a
handoff artifact, **not** a smoke result, native run, BT-009 receipt or promotion.
Existing downstream execution gates are unchanged. Source changes require a new
bound/reviewed contract; old artifacts cannot simply adopt the newest commit.

## Released representation transitions

`app.contracts.representation_transition.representation_transition_evidence`
compares the frozen candidate representation with a released implementation's
representation. Both complete document hashes remain mandatory. Only the explicit
narrative fields (operator rationale, member selection rationale, overall rationale
and rejected alternatives) are excluded from the additional operational projection.
Clock, basket, order, operators, parameters, inputs, outputs, fitting and selection
boundaries must match. Unknown fields fail closed. Every narrative change is retained
in the evidence for independent execution-handoff review: matching operators do not
prove the prose scientifically equivalent.

This diagnostic does not rewrite either document, approve a transition, bypass
native digest validation or dispatch execution. Source/bundle custody must be verified
by its caller. The November 25 retained candidate replay preserved ten narrative
changes and both original full hashes. Focused and adjacent backend tests: 207 passed.
Execution qualification materialization and production wiring remain outstanding.

The native prototype `bt.governance.released_execution.prepare_released_execution_contract`
replays both ready native plans against current bindings, preserves all declared
data identities except the explicitly refreshed producer receipt, and retains the
original template and immutable-contract digests in a new lineage record. It
requires unchanged partition names and timezone-aware boundary instants, including
equivalent `Z`/`+00:00` notation. It does not modify the released YAML. Both its
single/basket fixtures and the retained real-input packet replay pass; 34 native
binding/planner tests pass. This is not a registered execution qualification:
custody checks, worker/controller wiring, independent execution review and separate
task authority are still required. No new runtime path is enabled by this prototype.

## Two continuity modes

Default: `author_continuity` omitted or `reconstructed` in the approved evidence
context. Existing behavior retains the workspace and diagnostics, reconstructing
bounded context for ephemeral author calls. Old contracts are not rewritten.

Opt-in: `author_continuity: session`. The installed Codex CLI 0.146.0 exposes explicit
`exec resume SESSION_ID`; its help/argument parsing was checked without inference.
The adapter starts an author with structured JSON events, records the emitted thread
UUID, and resumes that exact UUID for repair. It never uses `--last`, thread names
or silent fallback. Source, approved contract, model, billing lane, effective Codex
home and workspace path must match. A changed binding or lost session ID stops
safely; it does not create another paid conversation implicitly.

Session mode requires the same surviving workspace. Reconstructed mode retains
the existing tested cross-attempt patch restoration. Moving a persisted author
session to another workspace/machine is deliberately unsupported until explicitly
qualified; it requires a governed successor, not silently rebinding the session.

Billing configuration is applied once by the shared process runner. Method
authoring/review adapters and the session adapter pass un-routed arguments to it;
subscription and API-lane regression cases guard against duplicate routing.

Reviewer and adjudicator calls remain separate ephemeral read-only invocations.
They do not resume the author's session, and author events are excluded from the
review/adjudication context summaries. Registration and provider-correlation policy
still belong to the evaluator router; this is not a claim of independent model families.

Both modes use the same episode call/repair/deadline budgets and deterministic
gates. Quota-before-launch can wait without inventing a session. A crash after an
unrecorded launch remains charged and requires explicit recovery. Session files
remain in the protected Codex home and are not Git artifacts.

## Controlled comparison

`test_accepted_method_handoff.py` exercises three implementations in both modes:
threshold ties, aggregation, and causal lag. Each starts with an injected failing
implementation, repairs in place, passes real pytest subprocesses, independent
scripted review and the existing validation/bundle path. Both modes use identical
contracts and budgets; each needs two author calls and one repair. Tests also reject
changed source/scope, absent registration, tampered plans/profiles and session drift.

These are synthetic fixture repositories with scripted model responses, not a full
Bulletproof scientific run or a live-model A/B experiment. Runtime, completion and
repair counters exist, but latency/token/cost superiority cannot be inferred from
these fixtures. Genuine session performance and real candidate commissioning remain
unmeasured. The native Bulletproof environment was separately checked for importable
NumPy, pandas and pytest; that check is not a dependency lock or native run receipt.

Rollback: keep reconstructed continuity and omit the new handoff for legacy
contracts, preserving their original gates. Do not strip it from already approved
new contracts or erase episode history. The campaign loop remains stopped unless
separately authorized to resume.

Verification on 2026-11-17: 200 focused worker tests passed, covering method
episodes/reviews, accepted-method handoff, author sessions, engineering policy,
provider capacity and billing lanes. This is implementation evidence, not live
commissioning acceptance.

## Released execution handoff increment (2026-11-25)

The genuine engineering task `a9d62708-b1d3-4aa6-83cd-457fba53bb22`
completed focused tests, independent code review and full native validation;
its accepted implementation was released as Bulletproof `52d882e`.
The source-bound review campaign `4450d67e-8488-4293-9a48-b33e84f53a8e`
has accepted method reviews but remains at `materialize_accepted_method_handoff`.
Neither fact is a native execution receipt or backtest authorization.

Local, not yet deployed, preparation helpers preserve the full accepted and
released representation digests while exposing narrative-only differences for
independent review. Native contract preparation replays both validation plans,
preserves partition instants, and records prospective source/data bindings without
rewriting the historical template. Preparing a new card stops before confirmation
unless an approval names that exact prospective card digest. These helpers do not
verify external receipt custody themselves; their controller must do that.

Verification: 207 control-plane tests and 38 native preparation/planning tests
passed. The preparation boundary tests isolate compilation dependencies; they do
not prove a complete production handoff. Worker/controller materialization,
independent review of the exact execution artifact and separately governed smoke
dispatch remain outstanding. No market-data execution was started by this increment.

The next local increment adds an explicit `prepare_execution` worker/native stage,
separate from commissioning and execution. Unknown native stages now fail closed
instead of entering the execution fallback. Compact qualification transport retains
the paired released-binding and representation-transition documents, verifies their
digests and source binding, and rejects missing or modified evidence. Prospective
card transport preserves the full binding and narrative evidence for controller review.

Read-only replay against the genuine retained candidate and planning inputs produced
draft card `0cd6b94210468222118fee81fd7c13ecb1fb016194541be453671cc8b023ef8f`
and binding `9a70cb4e4922ed39553f5f476b5a11b5123500103fc1fb7c56187aa58c8eebba`.
This was a local helper replay, not production worker execution, approval or durable
publication. It used zero model calls and did not run market data.

Verification: 150 focused worker regression tests and 177 native runner, strategy,
preparation and planning tests passed. Controller publication/materialization remains
unwired. Before smoke dispatch, full admitted dataset identities must survive the
execution transport rather than being trimmed to its legacy subset, and the exact
prospective artifact must pass its own approval/review gates. All changes in this
increment remain local and undeployed.

The dataset transport gap is now repaired locally: a strict native binding variant
retains all admitted metadata, while legacy bindings preserve their previous shape.
Instrument aliases, partition identities and admission digests must agree; unknown
or partial native identities are rejected. Multiple partitions may be retained
without inventing a singular partition identity. Campaign stage construction carries
full bindings for preparation and released-artifact execution only.

Read-only replay of the genuine planning bindings through worker serialization and
Bulletproof's independent identity verifier passed with all 19 declared identity
fields retained. No data execution was performed. The backend campaign/method suite
passed 263 tests; its routed-review fixture was updated to provide the input contract
that production review-context validation already requires. Durable preparation-task
materialization and execution-review routing remain outstanding and undeployed.

Durable preparation materialization is now implemented locally behind an explicit
`method_execution_preparation_requests` entry in the immutable campaign. Accepted
method review alone does not enable it. The controller locks campaign ownership,
checks current method authority and independent acceptance, verifies successful
engineering and native-plan custody, binds the mandate's released capability, and
creates one approval-gated `prepare_execution` task. Reconciliation reuses that task
only when its parent and complete contract match. Lease-time authority checks retain
the parent method gate. Preparation cannot authorize market-data execution.

Research context comes from the retained original draft, not a new retrieval call
on each reconciliation. This prevents changing retrieval results from producing
duplicate task identities. A read-only snapshot replay against the genuine retained
engineering receipt, method packet, plans and mandate catalog passed custody checks
and built contract `0b0ab835b7df2d487e0d98834edf555ebbfb7b45de241fbe5231278d0457ed17`.
The replay substituted snapshot transport for database path resolution and did not
create a production task. Durable post-preparation publication, exact-card approval,
execution-artifact review routing and smoke dispatch remain to be integrated.

Post-preparation publication and exact-card confirmation are now connected locally.
The backend reconstructs the permitted contract rebinding from the frozen template
and preparation inputs and checks the complete returned lineage. Changed scientific
fields, even with recomputed output hashes, fail verification. An idempotent campaign
event records the task, plan, card, preparation and binding digests; complete evidence
remains in the immutable task result.

The existing founder-confirmation mechanism receives the exact card plus retained
prepared evidence. Only its matching, current approval permits deterministic native
compilation; the compilation task remains `prepare_execution`, not `execute`.
Cancelled/failed confirmations are not resurrected, and compilation failures have
explicit next actions. These controller changes are not deployed or commissioned.
Independent execution-artifact review routing and authorized smoke dispatch remain
outstanding. The focused backend suite passed 280 tests before the additional
terminal-state and approval-plan guards.

Independent execution-review routing is now connected locally after deterministic
compilation. The controller verifies the confirmed card, prepared contract, lineage,
representation transition and every deterministic gate before routing. Producers from
method design, engineering, native planning, preparation and compilation are excluded
from reviewing their own artifact. Both strategy-specification and causality reviews
bind the exact card and artifact-bundle digests. Rejections and invalid completed
review evidence produce explicit repair states; acceptance records an immutable review
reference but does not authorize a smoke run. The backend suite passed 292 tests before
the additional invalid-completed-review guard. Native compilation replay, deployment,
source-bound commissioning and smoke dispatch remain unproven/outstanding.

Native compilation replay now passed on the retained real candidate: prospective
preparation, synthetic offline card confirmation, native compilation, worker handoff
and backend exact-artifact verification. The artifact-bundle digest was
`a844223fa596245ae2f54c9fc89c145aa42eb3efcac55f728ded6b7b78a756d5`.
The independent-review gate remained false. A synthetic reviewed fixture then passed
worker smoke-policy checks and native plan verification, while the native governed
review verifier correctly rejected that synthetic assertion. No API write, model call
or market-data execution occurred; these are replay results, not production approvals.

Smoke task materialization is implemented locally behind `allow_smoke_execution`
(default false) in the frozen preparation request. Accepted execution reviews plus
this explicit scope may create one risk-1, approval-required commissioning task using
the exact smoke start and target-tail end, not the scientific window. Lease checks
revalidate method authority and the current execution review. Native validation-plan
transport is explicit and source-bound. Tests: 299 backend and 66 focused worker
checks passed. Rollout, fresh source-bound commissioning authority, observed native
smoke execution and terminal publication remain outstanding.

Terminal commissioning publication now uses the existing BT-009 bridge and its
consumed-approval, artifact, projection and memory checks. It records a separate
idempotent `smoke_outcome_published` event, never a scientific campaign attempt.
Publication rejects scientific/capital/promotion claims from a commissioning run.
Completed-result collection precedes expiry checks so an expired authority cannot
strand an already authorized result; it does not reopen the campaign or grant new
execution. A campaign row lock serializes duplicate reconciliation.

Validation on November 25: 304 backend regression tests passed, followed by 40
focused preparation/publication tests including the expiry-collection regression;
66 worker tests and 177 Bulletproof native tests passed. These are local checks,
not a production smoke receipt. The live review-only campaign remains at
`materialize_accepted_method_handoff`; deployment and exact-source successor
authority are still required before execution.

## Released Preparation Rollout (2026-11-25)

Control-plane `b376146` and Bulletproof `b9b19c2` are pushed to `main`.
VM2 API was rebuilt and verified healthy, with Alembic at `d0a2b5f83c71`;
both VM1 capacity executor slots were restarted after confirming no active
Bulletproof tasks. Final regression coverage: 318 backend, 66 worker and
177 native tests passed. No migration or historical evidence rewrite occurred.

The founder approved mandate
`ALPHA004-AEP007C-RELEASED-PREPARATION-SMOKE-20261125`, exact digest
`6846ad9f5d5f0b23d511a81b484111c5345b8a40ded304044ef7f0d6c965785d`.
It is active until November 26 at 01:39 UTC, bound to `b9b19c2`, with discovery
disabled and separate campaign/task approvals still required. Unchanged BTC
data was re-attested as receipt `2bf717d6-7337-4112-be6d-0b402ba43794`.
Governed coverage task `c1a51f2f-e37d-4f9d-b1af-6a7632fb2ce2` succeeded;
native planning task `72cababc-a078-4017-b480-d093b22aaa90` was queued.
This proves deployment and coverage, not smoke execution or full certification.

The successor campaign `1ce946cf-ae1b-447f-abe7-5448f85e717c` was explicitly
activated at digest `8cc362dac39dfb5908f268503fe0ca11b67959cacd668b6c8543bf4c94ceacd6`.
Native planning, draft and method refresh succeeded; both independent method
reviews approved. The first preparation task failed only when constructing the
worker result: its 40,448-byte handoff exceeded the shared 32 KiB wire limit.
The retained native preparation artifact remains on disk, not in Git.

A mirrored, bounded, digest-checked research handoff codec now supports lossless
transport for preparation, qualification and publication. It preserves the 32 KiB
wire limit, caps expansion at 512 KiB, rejects corrupt/trailing/compression-bomb
payloads and leaves small legacy objects unchanged. A read-only replay of the
actual failed output produced a 13,776-byte envelope and passed exact backend
preparation verification without rerunning native work. This transport check is
not a successful production retry; the failed attempt remains historical evidence.

The controlled retry succeeded, exact card confirmation completed, and native
compilation task `ac83c111-6860-454b-8a27-dd8b5bd63a58` succeeded. Execution review
then exposed absent lease-time producer snapshots. Repair `975dd8e` records
profiles prospectively for preparation/compilation and accepted-method engineering,
and exposes `restore_execution_producer_identity` rather than an HTTP 500.

Historical recovery is deliberately narrower than using current registrations:
only one hash-valid profile for the recorded agent/package, valid at the exact
lease time, can supply a derived identity. Its evidence is bound into the review
subject as `historical_producer_resolutions`; no original event is changed.
Malformed existing snapshots are not eligible for fallback. Preparation and
compilation have candidate historical profiles; the engineering producer does
not. Its retained episode contains a task/source/contract-bound author session,
model and provider, but recovering that identity still requires a separately
validated evidence-backed attestation. Independent execution review and smoke
remain unproven. Historical-profile and routing regressions passed 99 tests.

The engineering fallback now accepts only the bytes of an already registered
`engineering-episode.json`, matching its hash, size, agent, attempt, source and
publication interval. It cross-checks the episode against the immutable lease
and completion, including the author session, contract and terminal bundle
receipt. An orchestrator-only import appends a separate task event; it does not
rewrite the old lease or register a retroactive profile. Routing revalidates the
evidence on every use. Historical machine/runtime remain explicitly unknown and
count as shared correlation, never evidence of independence. This is
worker-reported provenance, not a provider attestation. The actual retained
engineering artifact passed read-only validation; 120 focused recovery, routing,
preparation and lease tests passed. Production review and smoke are still pending.

Production import and routing then succeeded on deployed `b638504`. Route
`b258011b-0025-4158-a12c-c1061dc6b9e0` ran both reviewers against `b9b19c2`:
specification task `3d2a47ac-efaa-47e2-9e46-ab6dede1aafa` and causality task
`a080c433-54ee-4720-8586-4d7b4f627771` completed with **rejection**, not approval.
The campaign now requests `repair_prepared_execution_artifact`; no smoke task
or market-data backtest was started.

The native trace confirms a production/synthetic parity gap: the synthetic
registered-runner fixture injects membership evidence and its contract digest,
whereas the production assignment must supply actual admitted evidence. The
catalog's BTC membership records are optional metadata explicitly marked
`execution_eligible=false`, not a usable receipt for the full experiment window.
Do not synthesize or retroactively assert that eligibility. A source-bound
correction must also distinguish runner-owned split/tail guarantees from
strategy responsibilities and resolve terminal-record schema requirements.
The shared resampler's count/endpoints test admitted interior off-grid
timestamps; an unreleased general fix now requires unique minute-aligned
constituents, with 5m/15m/30m/2h regression cases. An unreleased native preflight
also stops missing/rejected membership evidence before loading market panels
or evaluating variants. These repairs do not grant new source or execution
authority. The currently approved campaign permits zero new author calls.

Correction mandate `ALPHA004-AEP007C-EXECUTION-READINESS-20261125` is proposed,
not approved, at digest
`e40836d5d25ed53601b91b5329913d6b80eb16b0790c04eea4175fc33b5202dd`.
It retains `b9b19c2` and existing scientific/data constraints, allows a separately
activated four-call/one-repair engineering episode, and grants neither source
release nor market-data execution. The unreleased general native repairs passed
167 targeted tests plus 28 retained method tests; no new paid authoring ran.

Offline adjudication evidence narrows the logging finding: the existing
`required_observation_logging_evaluation` explicitly accepts a distinct
`terminal_no_observation` schema without measured signal fields. Three real
native-terminal regressions pass for negative/invalid/failed outcomes; a fourth
regression proves the shipped immutable contract lacks the production membership
binding without fixture injection or mutation. These tests do not overturn the
independent rejection or supply absent membership evidence. The runner already
replays validation plans and provides bounded splits to the evaluator; the next
review must trace that ownership, rather than infer absence from one module.
General reviewer guidance now requires this production-path trace and explicitly
distinguishes synthetic overrides, smoke/scientific mode and terminal records.
Worker prompt regressions passed 22 tests (12 existing cases skipped).

The founder subsequently approved correction mandate digest `e40836d5...b5202dd`;
its live state is active until November 26 at 02:21 UTC. Inactive campaign
`b3d062fb-7d33-4a17-af71-e8f04a98990d`, exact digest
`8e5e3e17ad87c9f3460dceb3359dac39c3dd3b083a51e41736213ff2cbd15d89`,
retains both rejected execution reviews and awaits separate activation. It allows
one static refresh, fresh method reviews and separately approved four-call,
one-repair engineering, not source release or market-data execution.

Prospective engineering producer profile `8286323e-4936-4589-9da2-9c3236c9a85b`
was registered against the currently deployed package and heartbeat runtime.
Its `engineering_producer_only` review kind cannot satisfy independent review
assignments. A live read-only lease-identity check passed. This registration is
not retroactive evidence for the historical engineering task.

### November 25: bounded corrective engineering dispatched

The founder activated campaign `b3d062fb-7d33-4a17-af71-e8f04a98990d`
at the exact `8e5e3e17...bd15d89` digest above. Fresh independent method reviews
`ffc5ef2f-d502-443b-b5b7-f910e6943791` and
`26208b42-6b6e-4c50-a31a-ff5830319bac` both approved. This accepts the method
specification, not observed eligibility, calibration adequacy or a backtest.

Engineering materialization then exposed a transport limit: the lossless
470,917-byte evidence document fit the expanded bound but preset-3 XZ exceeded
the wire bound. Control-plane repair `0e3b86b` retries preset-6 compression only
when necessary; neither evidence nor bounds change. API/worker decoder parity,
memory bounds and handoff tests passed (67 tests), and the deployed API then
materialized the real contract successfully.

Task `5a03ff8e-0454-42c1-8329-92c2914f5807`, plan digest
`9ea9ee96b165ab2f3834c5e4549f4b4b2e4be96f6775eb3b5967eee4ad9a6765`,
was approved through the unexpired bounded task delegation and observed running.
Only this engineering task was queued during dispatch. The engineering agent
was drain-paused again immediately after lease acquisition, allowing this task
to finish without admitting unrelated work. Its bounds remain four model calls
and one repair, synthetic tests and independent code review. Real membership
evidence remains absent; no source release or market-data execution is granted.

The task subsequently failed at independent review after consuming its four
model calls and one repair. The first worker-run focused suite passed 154 tests,
but review rejected incomplete genuine receipt admission and replacement of
scientific outcome-path tests with `await_data` assertions. The episode
automatically invoked its bounded repair, without an operator code patch. Its
second worker-run focused suite also passed 154 tests. Fresh review confirmed
restored scientific paths but rejected self-attested production eligibility:
caller booleans and an unkeyed hash over public source/producer identifiers do
not establish trusted listing or membership evidence. It also identified stale
test names and provenance claims. No full-suite acceptance, release or backtest
followed. The engineering agent remains drain-paused.

Proposed mandate `ALPHA004-AEP007C-TRUSTED-ELIGIBILITY-20261125`, digest
`4ef61b32fd6fa8afc4be39d563eb99434d88681cb722fd0a58bfa1565829604d`,
was awaiting founder approval and has now passed its original November 26 02:21 UTC
expiry. It preserved the science/source/data limits and proposed a separately activated
four-call/one-repair successor requiring an independently trusted receipt
binding, forged-receipt rejection and separate synthetic outcome-path coverage.
Missing actual eligibility remains `await_data`; historical charges remain
intact. Automatic bounded recovery is observed here, but successful autonomous
engineering and discovery-to-results certification remain unproven.

### November 26: data prerequisites before paid work

The method-engineering commissioning path now requires an explicit
`method-data-prerequisites-v1` document in the immutable evidence catalog,
referenced by the `data_prerequisites` dependency. The prospective compiler
`alpha_data_prerequisites.bind_data_prerequisites` binds candidate/source identity,
normalizes duplicate checkpoints and refuses to replace an existing declaration.
It does not alter approved records or select scientific requirements. Checkpoint
completeness must be reviewed in the successor; no prose parsing infers eligibility.

Before creating method-author work for an engineering campaign, and again before
engineering handoff, the control plane resolves declared clocks through the
registered point-in-time catalog/reference resolver. Resolved partitions must
belong to the candidate's bound catalog, dataset and partition digests. Missing
declarations or identity conflicts require assessment. Unavailable registered
evidence yields `produce_admitted_method_data` / `await_data`, not paid repair.
The existing durable candidate-deferral path advances the queue and preserves
history with zero scientific trials. The blocker projection now honors the
recorded typed disposition's owner and recovery condition.

These checks establish only declared checkpoint readiness, not whole-window
coverage, science, calibration or execution certification. The existing native
plans and scientific gates remain required. Legacy packets without declarations
cannot be silently grandfathered or edited; they require reviewed successors.
The deployed initial increment covers the opt-in method-engineering commissioning
path, not a claim that every other research lane has equivalent enforcement.
The subsequent local repair also gates released-strategy execution preparation
before method-task creation and before paid method review. Reusing released code
does not waive the accepted method's data prerequisites. Regression tests assert
that neither review nor preparation is dispatched when required evidence is
unavailable, and that approved campaign specifications remain unchanged.

A read-only probe of retained BTC catalog `4f007cc5...e594141` at
`2025-05-18T20:00:00Z` returned `No market-data catalog was known at that time.` This
demonstrates a registry provenance limitation, not absence of BTC price bars.
Do not substitute today's knowledge clock or fabricate historical metadata to
clear it. The previous candidate and expired campaign have not been rewritten.
Controlled tests cover rejection before paid review/engineering and durable
deferral followed by sibling cursor selection; live successor commissioning
and producer selection of complete reviewed declarations remain outstanding.

Live registry inspection on November 26 found 39 snapshots, with catalog
`as_of` values from August 26 to November 13, 2026. The bound BTC catalog has
`as_of=2026-09-25T12:17:31.209761Z`; its partition spans January 1, 2021 through
May 18, 2026 at 18:50 UTC. Both partition and membership availability are recorded
at that final timestamp. The May 2025 probe is inside the partition, but precedes
its registered availability and catalog knowledge dates. Subsequent inspection
of the retained `accepted-method-evidence.json` confirms this is the training
start in `accepted_method_handoff.packet.proposal.method.eligibility_policy`.

The current resolver requires the catalog snapshot itself to be known at the
requested historical clock. Consequently none of these 39 snapshots can resolve
a knowledge clock within the historical envelope ending August 8, 2026. This
is a system-wide provenance limitation for that resolver, not proof that all
historical lake data is absent or scientifically unusable. A retrospectively
registered historical archive and contemporaneously known universe membership
are distinct claims. Any future support for retrospective archives needs explicit
provenance semantics and independent review, not backdated registration or a
substitution of today's knowledge clock. Until the accepted method's required
claim has genuine evidence, it remains a data prerequisite rather than an
authoring repair. No eligible live sibling has been demonstrated by these checks.

Commit `ab10ab4` is deployed on VM2; the API health check passed and the running
container imports `app.services.alpha_data_prerequisites`. Paid commissioning
remains paused. The next producer increment must explicitly declare the claims
needed by the method, preserve source/partition binding, and route unavailable
provenance to data assessment before requesting new engineering authority.

The subsequent local repair adds structured resolver failure codes to retained
data-prerequisite diagnostics: catalog/reference knowledge-time gaps, partition
availability, partition admission failure, source availability and universe
membership are distinguished without parsing exception messages. They still
defer with no paid repair; this does not grant historical provenance or relax
the resolver. Producer-side declaration completeness and an authorized live
successor remain outstanding.

`POST /v1/research/alpha-campaigns/data-prerequisites/assess` provides a bounded,
orchestrator-authenticated, read-only prospective check. Supply a typed
`declaration` and candidate `dataset_bindings` before seeking approval. It returns
the canonical declaration digest and either `declared_checkpoints_resolved` or
a typed blocker/disposition. It never creates a task, approves a declaration,
changes a campaign or certifies completeness; callers must still review the
requirements and bind the resulting declaration into an authorized successor.
The dispatch-time check remains necessary because this assessment is not a
reusable execution permit.

The same retained packet's `discovery_candidate.scientific_specification.
missing_data_policy` explicitly makes absent independent listing/membership
evidence a terminal validity limitation. This is not merely an assumption
introduced by the new gate. Reinterpreting a fixed-instrument historical archive
as adequate for that claim would require a separately reviewed method change;
the existing accepted contract cannot be relaxed silently. A live read-only
campaign inventory found zero running campaigns, 67 `completed_no_candidate`,
63 `needs_attention` and 12 cancelled. These are campaign counts, not backtest
results or counts of distinct hypotheses. No active sibling progression is
proven, and expired legacy records must not be relabeled to imply otherwise.

### November 26: deployed prospective assessment

Commit `ec2885e` is on main and deployed. The live read-only assessment of BTC
candidate digest `6a898c4ff9cd928c7de2074fe4123a1cc6e21c7dfa0928a2ec0432ae6d12bb88`
returned `await_data`, owner `data_admission`, `automatic_repair=false`, and
`catalog_not_known_at_requested_time`. The declaration digest was
`eb5cb0ec66253145c7ae562bf803d33a44d329fc3ccb45dd0da55c4eeaa153de`.
This was a prospective checkpoint diagnostic, not a reviewed complete declaration
or a mutation of an expired campaign. All 324 targeted tests passed before release.

A separate diagnostic held `effective_at=2025-05-18T20:00:00Z` fixed and queried
`known_at=2026-11-26T22:45:03.741116Z`. The existing resolver returned HTTP 200
and the expected bound partition digest `9a211d88...4aacb`. This establishes
present retrospective access only. It must not be supplied as historical
decision-time eligibility, nor substituted into the accepted method declaration.

Two distinct prospective paths require a decision before further commissioning:

- Preserve historical knowledge-time claims and acquire genuine source evidence
  for listing, membership and availability. Current catalog registration alone
  does not establish those claims.
- Prepare a separately reviewed retrospective fixed-asset research successor,
  explicitly limiting its population and claims. Causal feature construction,
  outcome separation, source integrity and scientific validation still apply;
  retrospective selection cannot imply survivorship-free historical tradability.

Neither path is implemented or approved by these diagnostics. The old candidate,
reviews and charges remain unchanged. Discovery, representation and engineering
agent pauses were verified after deployment; no new paid episode was dispatched.

### Retained listing evidence versus eligibility proof

Read-only inspection of registered producer receipt
`2bf717d6-7337-4112-be6d-0b402ba43794` found `result.instrument_reference`:
BTCUSDT / Bybit / perpetual, status `Trading`,
`first_seen_ts=2020-03-15T00:00:00Z` and
`last_seen_ts=2026-08-08T21:50:39.763308Z`. Its instrument-manifest digest is
`392232e9020ee50eb17f6a1a83f9c3e5436f6e7e0bc60917e17d644a4d0d218e`.
Thus listing metadata is retained; the limitation is the strength and temporal
scope of the claim, not complete absence of instrument metadata.

The current native Bybit adapter maps exchange `launchTime` to `first_seen_ts`
and acquisition time to `last_seen_ts`. This explains current field semantics,
but is not itself proof of the code or upstream payload used for that historical
manifest. Native admission retains the instrument row and manifest digest;
control-plane admission constructs reference/membership records using panel
end time and registration time. Neither transformation produces an independent
historical status-change ledger.

| Claim | Retained evidence | Remaining boundary |
| --- | --- | --- |
| Present access to exact BTC archive | Registered partition resolves at current knowledge time | Not a historical knowledge-time claim |
| Instrument identity and reported launch date | Registered instrument row and manifest digest | Original source payload/acquisition custody must be checked before strengthening the claim |
| Historical listing continuity | No continuity ledger established by this inspection | Launch date plus later Trading status does not prove uninterrupted status |
| Historical universe membership | Generated `alpha-preregistered-selection` record | A research basket selection is not an independently observed historical universe |

Do not backdate catalog registration, infer continuity from price bars, or claim
that inspecting this receipt has cleared the accepted method's terminal validity
limitation. No new execution or review authority is implied.
