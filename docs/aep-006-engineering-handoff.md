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
