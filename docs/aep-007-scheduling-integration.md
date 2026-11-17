# AEP-007: scheduling, authority and visible recovery

Status: **in progress; commissioning is not complete**. AEP-005/AEP-006 are not
the production default. Controlled fixtures are not genuine-candidate receipts.

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
These provisioning changes are locally tested, not yet installed or registered.

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

- Deploy and verify this bounded correction increment.
- Release, register and install the tested dedicated method-designer runtime.
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
campaign or approval digest has been created by this increment.
