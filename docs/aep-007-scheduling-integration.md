# AEP-007: scheduling, authority and visible recovery

Status: **in progress; commissioning is not complete**. AEP-005/AEP-006 are not
the production default. Controlled fixtures are not genuine-candidate receipts.

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
