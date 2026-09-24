# Native capacity-loop validation

2026-09-15: local source validation, production activation pending.

- Existing Bulletproof global capacity scheduler reused; ALPHA execution now has
  a typed native queue adapter and bounded spawned classic-engine variant pool.
- Resource estimates no longer understate requested workers. Startup reservations,
  CPU headroom/load, RAM hysteresis, exclusive leadership, orphan reservations,
  exact repository dispatch, assignment integrity, dead-owner rejection, duplicate
  refusal and already-launched pending children are covered.
- Native focused suite: 32 passed, including real classic-engine serial/parallel
  parity on two variants and 230 trades per variant; the additional shared-budget
  two-job launch test also passes (seven admission tests in the final focused rerun).
  CSV header order differs under spawned process hash ordering, but every named
  trade/equity field compares exactly, without float tolerances or dropped columns.
- Full worker suite: 276 passed. Backend discovery/conversation tests: 14 passed.
- Shell syntax and systemd unit verification passed; systemd reports unrelated
  existing snapd/netplan warnings. Ruff verification is part of final local checks.
- VM1 sampled 36 CPUs, 71 GiB total and 64 GiB available RAM. This is a point-in-time
  observation, not a guaranteed performance or calibrated memory requirement.
- No production services or credentials were changed, no backtests were queued,
  and no orders or capital actions occurred. Two-job live replay and BT-009 terminal
  publication remain required before operational closure.

See [activation runbook](runbooks/alpha-capacity-governed-execution.md).
# Activation recovery correction (2026-09-15)

Live slot-2 registration stopped at charter creation: its charter bytes duplicated
slot 1 and the registry enforces global digest uniqueness. Slot 2 exists without
a charter. Bootstrap now names the executor slot in its responsibility and
supports explicit `--recover-registration`, validating the existing agent and
deployment before reuse. Lost slot-2 credentials are replaced through scoped
workload rotation, saved mode 0600, then finalized; slot 1 is untouched.
Regression tests cover refusal of implicit recovery and successful scoped recovery.
The deployment-list fixture now matches the API's nested `{deployment, package}`
contract. It reproduced the live `KeyError: agent_id` before the bootstrap lookup
was corrected to unwrap `deployment`; deployment creation remains a flat response.
Privileged activation remains pending until the corrected script succeeds.

Activation succeeded at 2026-09-15 18:52 UTC. The capacity director and both slots
are active with zero restarts and successful authenticated idle polling. The queue
is empty; concurrent terminal BT-009 proof remains outstanding. Recent Telegram
failures predate activation: discovery cycles 019–021 crashed in Node/V8 with
SIGTRAP (-5), and older founder turns failed the reasoning contract. Discovery's
restricted subprocess environment dropped the service's jitless setting. The
executor now supplies fixed `NODE_OPTIONS=--jitless` without inheriting secrets or
arbitrary Node options. Existing discovery workers require restart to load this fix;
no failed task or old approval was replayed automatically.

## Approved mandate and discovery recovery (2026-09-15)

The founder approved `ALPHA004-CAPACITY-20260915`, mandate
`aae38741-7f41-40bc-8612-0ba266467a55`, against reviewed native commit
`a864ac0910890f98f457eb4140b28ede9921e91d`. Its immutable execution window is
2025-05-01 through 2026-05-01 and its existing data authority is Bybit BTCUSDT.
Fresh native admission receipt `09c3b6a6-b7d5-4efe-88a6-637259ab47ce` binds the
same panel to that commit. Admission does not establish complete funding coverage;
auxiliary availability remains a separate execution gate.

First intelligence task `A4-aae38741-001-I` failed three attempts because Codex
runtime initialization attempted writes on a read-only filesystem. SQLite and
log locations now use a private, mode-0700 attempt directory while credential
custody remains read-only. A subsequent live startup probe passed initialization
but failed authentication with `refresh_token_reused`; operator reauthentication
is required before productive discovery can be demonstrated.

Cycle recovery requires an explicit `task_resumed` event after its failure and
matching task/cycle/mandate/stage bindings. It preserves failure events, does not
create an approval, and cannot automatically replay an old execution instruction.
Two concurrent terminal BT-009 receipts remain outstanding, not inferred from
online services, local pool tests, or historical one-month results.

After operator reauthentication/restart, audited resume created attempt 4 on
2026-09-15 at 20:04 UTC. It still failed initialization under systemd confinement.
A matching read-only namespace trace established the remaining mandatory write:
`CODEX_HOME/installation_id` is opened read-write even with SQLite/log overrides.
The corrected units therefore use a private writable runtime home with a
read-only bind mount of the original `auth.json`, never a credential copy.
The installer creates only an empty mount target, does not truncate it on repeat,
and preserves strict filesystem confinement. Discovery disables plugin/app
integration so cached plugins cannot expand this bounded workflow.
The corrected namespace probe first reported temporary model capacity, then
completed authenticated inference with `runtime-ok` under the same read-only
credential binding. Privileged unit reinstall and productive recovery are still
required; the original and resumed failures remain retained.

After corrected production unit installation at 20:10 UTC, audited attempt 5
completed intelligence inference successfully at 20:13 UTC. It honestly
abstained from inventing a hypothesis because its immutable context contained
zero RI citations. Live comparison reproduced the query problem: the long
operating mandate returned zero hits, while focused momentum/cost, liquidity
and volatility queries retrieved cited uploaded literature under unchanged
calibration thresholds.

Discovery now runs at most four data-aware queries, rotates bounded conceptual
facets across cycles, retains query-level receipts and canonical citation
provenance, deduplicates objects, and rejects mixed corpus digests. Field presence
only guides retrieval; auxiliary availability and hypothesis feasibility gates
remain mandatory. Mathematical campaign authority requires a bound deterministic
or independent verification receipt, not source replay alone.

An explicit `recover-grounding` API creates a fresh cycle only for the expected
terminal, ungrounded, campaign-free cycle under an active unchanged mandate with
remaining cycle/hypothesis/trial budget and fresh citations. It requires a founder
actor and reason, refuses active stages and founder-idea reassignment, and retains
the old cycle/digest plus a recovery event. It does not change automatic cadence,
data scope, code approvals, execution approval or capital authority. Repeated
requests with the old cycle ID fail closed rather than creating duplicate work.
Successful inference and retrieval are not terminal backtest or two-job proof.
The current reviewed native drafting producer implements weekend momentum only;
other mechanisms require genuine native strategy engineering and explicit code
approval, not rewriting their questions to fit that template. The researcher now
receives the frozen eight-variant limit, one-year execution window, reviewed
native commit and preregistered-universe requirement in its supplied context.

Fresh-context recovery initially returned HTTP 500: two pending discovery events
both received sequence 10 because production sessions disable autoflush. The
transaction rolled back; no duplicate cycle was committed. Event append now locks
the mandate row and flushes pending events before reading the prior chain head.
An isolated PostgreSQL replay with `autoflush=False` exercises two event appends
in one transaction and checks contiguous sequence and digest linkage. The new
alpha-discovery CI job runs this database-backed regression on each PR and main
push; focused mocks alone are not accepted as this transaction proof.

## VM1 restart and orphan-lock recovery (2026-09-18)

An abrupt VM1 reset left capacity row
`0a611347-b2d6-4a5e-b23c-b0a88a476ea4` locked by a process from the prior boot.
The director now identifies locks by host, process and boot identity at startup.
It refuses to steal a live same-boot owner, but terminalizes a dead prior-boot
Hermes lease as `FAILED`, clears both lock columns and retains partial artifacts.
The retained failure reason is `capacity scheduler restart detected dead Hermes
lease owner; partial artifacts retained`; the original attempt is never rewritten
as successful or silently requeued.

Replacement row `32c713e0-c44d-4284-91d5-8b9147cccd2c` bound the same immutable
assignment digest and completed `DONE`. The production journal records one
`failed_dead_owner` recovery at director startup, followed by the replacement
launch and exit code zero. A post-recovery database audit found no locked rows.
The focused native recovery suite passes 10 tests, covering dead prior-boot
owners, live same-boot owners, retry limits and idempotent repeated startup.

The first one-year eight-variant run consumed about 4.1 GiB per worker. Production
admission therefore uses 4.5 GiB per requested worker, plus its free-memory floor.
On the 71 GiB VM1 this correctly serializes two eight-worker jobs when concurrent
admission would exceed measured safe capacity. Concurrency is a capacity outcome,
not a milestone assertion; the scheduler must not overcommit memory merely to make
two jobs overlap.

## One-year production execution continuation (2026-09-23)

Two genuine approved one-year tasks overlapped on VM1 from 2026-09-19 00:44 UTC
until 01:07 UTC. The impact-proxy job completed during that interval. The funding-
basis job continued until its original six-hour execution bound, retained the timed-
out attempt, and was requeued against the same immutable task after the reviewed
eight-hour package rotation. This is overlapping admission and execution evidence;
it is not a claim that both jobs finished concurrently.

The impact-proxy campaign `c2fa962a-4f56-41ad-aaae-d01263fa62a6` is terminal
`completed_no_candidate`. It retained one negative attempt with eight trials and
complete reproducibility, point-in-time, held-out, cost-stress, selection-bias,
independent-review and logging gates. BT-009 bridge
`f801d5eb-8b58-51b1-aa6d-bae405ddf928` is `complete`; its publication bundle digest
is `5b82fd5223a8b8298a8c1da4d88a5670f02ba9862fe445f32f85e29a99ab5f26`
and its independent disposition is `retain_negative`.

The replacement funding-basis task used four preregistered variants over the 2023
calendar year and four capacity-governed workers. Direct measurement under the
classic engine showed roughly 684 rows per minute for the slowest variant, which
would miss the former eight-hour ceiling. Attempt two was therefore cooperatively
released at the worker boundary, preserving its immutable task events and partial
workspace, before timeout. PR #351 passed 373 worker tests, was merged as
`9e7670af8bad73f503d2ee0fe74a3b6880e7ede5`, and rotated only the signed executor
package to version 1.3.0 with a 43,200-second ceiling. The unchanged plan digest
`98455e60da54f3833d4cbb5c3b57e786044bafb95f65e0ab7e458d6021897482`
was reapproved under the bounded risk-zero delegation.

Attempt three completed four trials and produced a 77,605,586-byte native receipt.
Its scientific outcome is negative because matched-control support was inadequate;
no out-of-sample, cost-stress, shadow, order or capital authority was inferred. The
full receipt is retained under durable bundle
`103cf716d7e079755b3e2963a1c338428ead1c4de2e8162078268edfbf84710a`
with manifest digest
`001cf628eb3aecdf4e6166b8ffe6ef1a4bb508551339a8b41b08845f613944bf`.

The original worker handoff could not place that evidence inside its 32 KiB result
contract. PR #352, merged as
`bd7674e8f7c21aebb3255191c6e2444c4d8762ff`, replaced the oversized payload with a
compact digest-addressed handoff and added an authenticated recovery endpoint bound
to the exact workload identity on the failed attempt. After RI-016 reconciled to
source epoch 577480 with incremental/full digest parity, recovery completed BT-009
bridge `596171f2-2e8b-57e8-a405-186552478300`, publication
`158843cb-2a03-5392-9ca3-04820cca146c`, and memory confirmation. The campaign is
terminal `completed_no_candidate`; complete evidence was preserved while the
bounded worker contract remained intact.
