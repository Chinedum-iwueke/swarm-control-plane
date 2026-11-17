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
