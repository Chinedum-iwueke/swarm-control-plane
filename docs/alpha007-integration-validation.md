# ALPHA-007 integration evidence

2026-09-15: implementation in progress; production closure is not claimed.

The native full-lake inventory accounts for raw, canonical and manifest objects,
supports legacy and market-specific paths, streams content SHA-256, records
Parquet footer bounds and fields, and retains corrupt/non-Parquet/symlink objects
with explicit dispositions. The protected CLI receipt grants no execution or
capital authority. Native inventory/admission/producer suite: 14 passed.

Hermes registers only the exact native inventory producer under DATA-002,
verifies content bindings and object accounting, rejects inferred execution
admission, and exposes a receipt-backed full-lake summary. An orchestrator-only
operation report binds the native VM1 inventory workload rather than allowing
arbitrary workload replacement. The discovery output schema now requires the
canonical hyphenated domain/cluster keys; context carries mandate liquidity
requirements and explicitly treats historic universe labels as optional metadata.

Full worker suite: 289 passed. Registry/discovery focused suite: 49 passed.
The full extended backend suite passed 831 tests with one optional database
test skipped, including the operation-report regression. Earlier PostgreSQL
transaction proof remains separate evidence.

Live inspection found 2,768 canonical Parquet files and approximately 185 GiB
across raw and canonical trees. No full content scan, production inventory
registration, DATA-003 quality admission, mixed-basket execution, expanded
mandate activation or two-job BT-009 closure is inferred from these local tests.
Next: supervised scan with periodic ledger heartbeat, immutable publication,
native coverage/quality receipts and hypothesis-specific basket eligibility.

Pre-landing review identified silent subtree omission, unsafe path reopening,
special-file blocking, nested-column timestamp indexing, unvalidated summaries,
and report lifecycle races. Follow-up fixes use explicit traversal failure,
no-follow directory descriptors and one regular file descriptor for hash/metadata,
scalar timezone-aware timestamp bounds, device/inode/size/mtime/ctime stability,
derived disposition/assets validation, immutable input bindings and row-locked
terminal transitions. Fresh verification: 834 backend tests passed (one optional
database skip); 19 native inventory/admission/producer tests passed.
Hermes PR #268 and Bulletproof PR #307 are open with CI running. No production
scan, quality admission, expanded execution scope or backtest is claimed.

Production pass: Hermes PR #268 merged at e9ef1696e and VM2 API rebuilt/recreated.
Running image sha256:0606f0664916a02c0fbd4fb0c1e6f0e133ffec53d85ed2064e4f5a529b886353
was healthy and exposed the scoped inventory route. Real operation
d3dfa5fd-924a-4574-a301-3aa005240686 acknowledged before its scanner started;
live API inspection confirmed heartbeat, PID and more than 27,000 accounted
objects. Exact filesystem counts revealed 1,846,467 raw files and 2,769 canonical
files, exceeding the 250,000-object single-envelope contract. The operator stopped
the attempt explicitly for this engineering mismatch, not an observation timeout.
The ledger retained its terminal failed receipt at 2026-09-15T21:03:46.496137Z and
process inspection confirmed both supervisor and scanner were gone. No complete
inventory publication occurred. Native bounded 10,000-object shards and window
quality are now under implementation; shard custody must be verified before the
next full scan. Initial combined native inventory/quality/admission tests: 29 passed.

The corrective implementation now emits bounded native shards, orders partition
paths globally (including directory/file prefix collisions), and binds a v2 root
to every shard. Hermes validates source/run/index/content bindings, completeness,
non-overlap and summaries before accepting the root. Incremental supervisor
publication preserves completed shard custody. Native quality streams verified
shards, keeps panel metrics rather than duplicating millions of raw-object records,
and reports non-panel adapters as unresolved. A dedicated quality CLI consumes the
same shard files; its protected-output handoff test passes. Quality registration
requires the bound inventory and content identity and grants no execution admission.
Fresh full suites: 850 backend passed (one optional database skip), 295 worker
passed. Native inventory/quality/admission/producer suite: 32 passed; lint passed.
The expanded shard pipeline is not yet production-replayed; the two concurrent
native backtests and wider approved research scope remain open.

Production continuation: native PR #308 and Hermes PR #269 are merged. All ten
native and eight Hermes CI checks passed; latest worker suite passed 300 tests.
VM2 deployed merge `2e3750da0`, with healthy running image
`sha256:cd1863c0c660b6d2661de024ad63ab6fba458f00b108564a06b5c582ae64e0c8`.
The bounded custody validators are installed. VM1 user systemd unit
`alpha007-full-lake-20260915.service` supervises run
`0767bfbe-206f-4290-9900-f9771b7a83b8`, supervisor PID 3873138 and initial native
child PID 3873684. Ledger acknowledgement preceded native scanning. Source binds
reviewed native `19d361ca6c09fd6bb45f2db24a22a70213661f81`; subsequent quality
uses frozen half-open window 2025-05-01 through 2026-05-01 UTC. Restart is disabled
to prevent accidental duplicate scans, and control-group shutdown cleans children.
The scan is in progress: no complete root, panel quality, wider execution approval
or overlapping scientific backtest is claimed yet.

Next source pass separates researcher visibility from mandate execution scope:
discovery reuses the inventory endpoint's receipt-backed summary as `lake_catalog`,
while `datasets` remains the exact admitted mandate inventory. Founder universe
hints now default to `all_eligible`; explicit stable/volatile hints remain valid.
The supervised researcher prompt requests hypothesis-specific cross-group baskets
and retains out-of-scope ideas as gaps, never as executable candidates. Regression
tests prove a catalog-visible ETH asset with no admitted binding still fails
DATA-002/003 availability. Focused backend tests passed 57 cases, including the
new context/default tests; the final strengthened context suite passed 23 cases.
Worker contract/prompt tests passed seven cases, and backend lint passed. This
source pass is not deployed and does not prove adaptive basket execution.

Pre-landing review caught chat grounding and planner instructions explicitly
overriding the new API default with stable/volatile. Both now default to
`all_eligible`, preserve explicit founder-selected group hints and retain admitted
mandate boundaries. Regression covers chat grounding, planner instructions and
typed proposal pass-through for both defaults and legacy hints. Full suites before
this correction passed 852 backend tests (one optional database skip) and 301
worker tests. Corrected planner tests passed 17 cases. The same exact inventory
unit remains live, with progress through the canonical Binance partitions; no
scan restart, complete inventory or concurrent scientific execution is inferred.

PR #270 merged and deployed on VM2 at `40ca4c759`; the running container confirms
the `all_eligible` intake default. All eight CI gates passed. Final backend suite
passed 852 tests with one optional skip; final worker suite passed 302. An earlier
concurrent worker/backend run hit an unchanged two-second child-start timeout test
before its child marker existed; the isolated test and subsequent full worker run
passed. The exact native inventory unit remains active across this API deployment.
Long-running VM1 planner/researcher processes still require a controlled restart
before the new prompt can be claimed loaded in those service processes.

The next engineering handoff source pass keeps bounded scientific evidence in the
executable engineering contract rather than only approval metadata. A validated
JSON text field (48,000-byte limit) preserves the planner's closed output schema.
Coder and independent reviewer receive identical untrusted evidence, bound to the
campaign/question/candidate digests, admitted dataset, frozen window, instrument,
tier, variant ceiling and unchanged no-capital authority. Changed or missing
discovery evidence prevents task creation. New approval-gated task scope includes
the existing native draft pipeline and assignment runner so generated cards can
actually be discovered without substitution into the weekend template. Historical
task scopes and approvals are not rewritten. Focused campaign tests passed 20,
proposal contracts eight, worker engineering/planner tests 30; lint passed.
This handoff source pass is not deployed and does not establish that a new native
strategy has been generated, qualified or backtested.

Independent review found excessive JSON nesting could escape normal contract
validation as RecursionError. All three consumers now reject decoding recursion
and depth beyond 32 with controlled validation errors before re-encoding. Changed
question and deep-JSON regressions pass: focused engineering/planner suite 32,
strengthened backend engineering handoff one. The full backend suite before this
review correction passed 852 with one optional skip. A repeated unchanged
process-group test failed before child startup under concurrent test load; its
test-only startup budget is now five seconds while still asserting actual timeout
and child termination. No production timeout or safety threshold was changed.

The corrected source pass is pushed as PR #271; independent review confirms the
recursion and question-mismatch findings closed. Fresh full suites passed 852
backend tests (one optional skip) and 309 worker tests. All eight PR #271 CI checks passed; deployment remains pending.
API ledger readback independently confirmed operation
`1f24f55d-45c3-4eae-b3ac-6c129023f9c3`, run
`0767bfbe-206f-4290-9900-f9771b7a83b8`, state running/phase inventory, heartbeat
2026-09-15T21:39:47.392352Z and 652 processed files. Process inspection confirms
the same supervisor/native child, not a restarted scan. Native template discovery
and evaluator receipt binding remain next engineering work; no scientific
independence is inferred solely from a hardcoded qualification gate.

Native generated-card discovery is now implemented in the source worktree. It
uses a normalized exact-question digest and source-reviewed JSON under
`research/hypotheses/cards`, reuses the existing hypothesis-card validator, and
rejects changed dataset/window bindings, self-confirmation, symlinks and excessive
parameter budgets. Unrelated/non-BTC questions cannot fall back to the BTC
template. Qualification variant counts are calculated from the real grid rather
than reported as a constant. Twenty combined native assignment/card/capacity-grid
tests passed in 64.89 seconds and lint passed. This source-only pass does
not establish semantic correctness, independent review, deployment or execution.

The next source pass replaces compiler self-attestation with explicit immutable
strategy-specification and causality/leakage reviews. Producer package/context
identities are frozen from authorized registry profiles at task lease, never
guessed retrospectively. Both drafter and qualifier identities are excluded from
review, including same-agent package rollovers; an explicit qualifier identity
binds the route primary. Qualification must replay the exact founder-approved
card, dataset, window and parameter grid before a new execution task is created.
Native execution checks the governed review before output allocation or compute;
missing review is retained as a zero-trial independent-evaluation failure, not
scientific falsification. Receipt hashes are replayed within authenticated
control-plane assignments, not treated as offline authority.

Native focused regression coverage passes 31 tests after the package-rollover
correction; the full backend suite passes 874 tests with one optional skip and
two existing deprecation warnings. Production reviewer registration/execution and engineering-author
provenance remain open; this source pass is not deployed and no genuine reviewer
receipt or concurrent scientific run is inferred from unit fixtures. The same
live inventory supervisor remains active, with progress reaching 1,600 objects;
complete-root registration and quality admission are still pending.

Automatic strategy review routing now creates an immutable route after exact
approval binding, using the actual qualifier as primary and every historical
producer as an exclusion. The existing router checks excluded producer
agent/package/context conflicts and disclosed correlation ceilings before
assignment. Missing reviewer capacity is retained as a blocked route with its
reason in campaign planning state. Focused routing/campaign tests pass 49; the
full backend suite passes 875 with one optional skip and two existing warnings.
Lint passes. Actual supervised reviewer execution and blocked-route recovery
after profile registration remain subsequent integration work, not demonstrated
by this source-only routing pass. The original inventory child is verified live
after 47 minutes, with no restart.

Blocked strategy review routes now reconcile when the active evaluator catalog
changes. Retry uses the same frozen subject, producer and exclusion policy,
appends an audit event and creates assignments only after all required kinds
are available. Unchanged catalogs emit no repeated retry events; assigned routes
are not replaced. Fifty-one focused routing/campaign tests pass and lint passes.
This closes source-level recovery, not actual reviewer provisioning/execution or
production deployment. The original inventory supervisor remains active and has
progressed to 1,730 objects.

Full backend validation passed 877 tests with one optional skip and two existing
warnings. Recovery additionally refreshes the route under a database row lock
before checking its state, preventing competing director cycles from assigning
the same blocked route concurrently.

The bounded read-only strategy reviewer executor is now implemented as source:
it binds the routed evaluator, immutable source commit, subject/card/artifact
digests and review kind, runs isolated Codex without trading authority, validates
typed approve/reject verdicts, and terminates its owned process group on lease
loss or timeout. Full worker coverage passes 319 tests; lint passes. It is not
registered in production workflow dispatch yet, and no genuine reviewer verdict
is inferred from its unit fixtures. Authenticated completion, reviewer-role
provisioning and engineering-author provenance remain open.

Runtime evidence supersedes the earlier live-scan observations: VM1's previous
boot ended at 22:15 UTC, with a new boot at 22:32 UTC. The transient unit and
native child vanished before root/shard publication. Operation
`1f24f55d-45c3-4eae-b3ac-6c129023f9c3` is now honestly terminal failed,
phase inventory_interrupted, completed 2026-09-15T22:39:30.485471Z, preserving
input digest `4911d259c0cca29a4b87161150c328a71c9db91d86e36961a5f372c1a11cc48a`
and 1,874 partial objects. No scan success or full-root receipt is claimed.
Recovery uses persistent user unit `alpha007-full-lake.service`, enabled with
user lingering verified yes. New run `93a00b1f-e9ae-4dca-931c-efc6bf9dd99a`
has supervisor PID 18776/native PID 18822 and fresh progress through 22 objects,
bound to the same native `19d361c` and frozen quality window. Recovery was
started only after terminal/missing-handle verification, not a polling timeout.
Boot configuration persistence is verified; an intentional reboot drill was not
performed. Complete inventory/quality registration remains pending.

Reviewer integration now uses the existing workflow loader, policy validation and
restricted dispatcher with a closed shared contract and pinned native repository.
Assigned evaluator routes materialize ordinary governed tasks; blocked routes
materialize none. SQL lease selection binds the exact evaluator agent, while
normal grant/capability/source access resolution remains required. Completion
runs only after authenticated running-lease verification, locks route/assignment,
replays the routed subject and compares actual lease-time profile/package identity
before recording the immutable typed verdict. Changed actors, packages, subjects,
review kinds, missing lease provenance and malformed results are rejected.
Required review-executor capabilities are checked during route selection so
profiles without an executable role do not produce invisible unleaseable work.
Full suites pass 885 backend tests (one optional skip, two existing warnings) and
320 worker tests; lint and diff checks pass. This source is not deployed. Actual
reviewer role/profile/grant provisioning, engineering-author provenance and a
genuine routed review receipt remain open. Replacement scan run
`93a00b1f-e9ae-4dca-931c-efc6bf9dd99a` remains live under supervisor 18776 and
has reached 1,221 objects; no complete-root or quality receipt is claimed.

## September 16 Rollout And Interruption Correction

PRs 271 (Hermes), 309 (Bulletproof) and 136 (Bible) merged after all their
CI checks passed. VM2 now runs merged Hermes commit `723029a1d`; migration
head remains `b1e7f9a03c62`. The recreated API is healthy and its image matches
the built image `sha256:45ec3459eb2e126d98b21f07921627ff4e52ab8b84446d13933ec2f1e3f725a4`.
Docker commands in SSH heredocs must disable stdin (`-T` and `/dev/null`) so
one-off containers cannot consume later rollout commands.

The previous live-scan observation is superseded: VM1 rebooted again at
23:01 UTC. Run `93a00b1f-e9ae-4dca-931c-efc6bf9dd99a` stopped at 1,753
objects without a full-root receipt. Its startup replacement failed at the
operator-host SSH preflight, before native scanning. The user unit is failed
with MainPID zero; no scan was restarted during crash investigation or rollout.
Guest logs show no recorded OOM kill or kernel panic, but do not establish the
hypervisor interruption cause. The Mac software update began after the freezes
and must not be cited as their cause. Full inventory, reviewer provisioning,
genuine review receipts and two concurrent terminal backtests remain outstanding.
