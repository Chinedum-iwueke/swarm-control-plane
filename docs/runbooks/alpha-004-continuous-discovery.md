# ALPHA-004 Continuous Evidence-Grounded Discovery

## Purpose

ALPHA-004 keeps the no-capital research loop supplied with real, predictive,
falsifiable questions. A VM2 director schedules immutable cycles. A read-only
Research Intelligence agent synthesizes cited evidence, failures, market
observations and portfolio gaps. A separately chartered senior researcher turns
that brief into typed candidate questions. A third, separately chartered data
representation scientist selects an outcome-blind basket, causal timeframe, required
fields and safe transformation while retaining rejected alternatives. The controller
validates exact candidate coverage, evidence, mathematics and DATA-002/003 bindings
before allocating DISC-009 attention and creating an ALPHA campaign.

## Authority

A founder approves one digest-bound mandate for at most seven days. The mandate
may authorize only historical no-capital research against its exact dataset,
window, instrument universe and trial budget. It replaces per-hypothesis card and
execution approvals inside that envelope. It never authorizes strategy code
changes outside the bounded ALPHA-003 hypothesis implementation allowlist, expanded
data, self-evaluation, shadow admission, orders, capital or live promotion. Existing
independent BT-009 evaluation remains authoritative.

Native hypothesis YAML, strategy modules, tests and the two named integration surfaces
may be generated without a second founder click when the task is created by the
campaign director, risk is at most one, its evidence explicitly denies capital,
orders, promotion and self-approval, and its paths remain inside the ALPHA-003
allowlist. Deterministic validation plus independent specification and
causality/leakage reviews remain mandatory. Every other engineering mission remains
approval-gated. A shadow candidate pauses the mandate for founder review.

Only one active `canonical_weekly` mandate directs the general loop. An explicitly
scoped `thematic` mandate may coexist only when it names the canonical mandate digest
as its parent. Canonicalization supersedes older general weekly mandates without
deleting their evidence or disturbing thematic children.

The primary historical window is the complete rolling 365 UTC days ending immediately
after the newest gap-free DATA-002 cataloged 1-minute bar. Wall-clock time and older
source-campaign windows are not silently substituted. A survivor may receive
a separate immutable deep-validation contract covering up to 1,095 recent historical
days only after primary-window survival, independent review and an explicit follow-up
contract.

## Candidate admission

Candidates must name a predictor, future target, horizon, direction, causal
timing, null hypothesis, finite parameter budget, point-in-time features,
mechanism, rivals and falsification criteria. Exact evidence object IDs and
content digests must replay against the cycle context. Instructions, vague topics,
descriptive statements, missing requested columns, missing volume/depth evidence,
weak liquidity scope and semantic
duplicates are retained as rejected candidates.

New mandates allow up to 100 instruments per hypothesis by default (hard schema
ceiling 128). The representation scientist may retain one instrument, mix historical
stable/volatile labels, or select a 30-100 member basket when breadth,
diversification or cross-sectional estimation is causal to the question. Large baskets
still require point-in-time membership, common-window, liquidity, DATA-002/003 content
admission and compute-capacity checks.

The bounded context includes a typed mechanism-primitive catalog extracted from the
exact native Bulletproof contracts. It includes declared CSI components and sources,
other registered indicators, gates, failure modes and falsification criteria. These
are prior designs an agent may adapt, challenge or reject. Catalog membership never
turns CSI, an index, a proxy or another mechanism into a proven signal.

Source replay makes an equation locatable and explainable. RI-014D automatically
requests exact, cached assurance when a candidate needs it. Campaign use requires
the resulting source-, expression- and level-bound deterministic or independent
receipt. LLM output is never its own verification receipt. Pending, replay-only,
invented, weaker or source-mismatched receipts are rejected from the campaign.

## Production sequence

1. Deploy through migration `a0d6e8f92b51` and rebuild the VM2 API. Assert both
   `/v1/research/alpha-discovery/mandates` and
   `/v1/research/scientific-fidelity/assurance/overview` exist in OpenAPI first.
   After every API-image rebuild, restart both
   `invariance-swarm-alpha-discovery-director.service` and
   `invariance-swarm-alpha-campaign-director.service`. These services run persistent
   containers from the API image; recreating only `swarm-api` leaves their old code
   resident and can silently preserve stale queue or campaign behavior.
2. Install `invariance-swarm-alpha-discovery-director.service` on VM2.
3. Bootstrap the `intelligence`, `researcher` and `representation` profiles on VM1,
   then install their three systemd services. The representation identity must expose
   only `data-representation` and `market-data-read` capabilities.
4. Run `worker/scripts/alpha004_mandate.py` on VM1. Inspect the exact dataset,
   recent 365-day window, universe ceiling and budget in Mission Control, then approve
   the mandate. Run `alpha004_canonicalize.py` against the selected active digest to
   supersede overlapping legacy weekly mandates.
5. Confirm the VM2 director and all three VM1 ALPHA-004 agents are active. Mission
   Control must report fresh heartbeats, `representation_selection` as a visible phase,
   the representation task ID/count, a running cycle and no unexplained stall.

The controller measures accepted or awaiting-data-admission depth across all active
campaigns. Below `question_queue_low_watermark`, it starts another bounded cycle while
`maximum_parallel_campaigns` permits. The one-hour cadence is only an idle fallback;
terminal negative, invalid, failed and duplicate-only cycles replenish immediately.

Mandate accounting is reconstructed from immutable cycle-start and terminal campaign
events. Completed, cancelled/invalid and shadow-candidate campaigns each debit their
hypothesis and trial counts exactly once; active engineering is exposed as in flight
and is not misreported as completed testing. A new mandate unions every complete,
admitted dataset binding from campaigns pinned to its exact Bulletproof commit rather
than inheriting only the first BTC binding. The broad catalog remains discovery-only:
the selected panel still requires point-in-time DATA-002/003 admission before a run.

## Failure and rollback

The director retains failed stages and stops a cycle at `needs_attention`.
Expired or changed mandates fail closed. Campaign failures feed subsequent cycle
context and novelty scoring. Rollback disables the four ALPHA-004 services and
stops creating new work; immutable mandates, candidates, campaigns, attempts and
event chains remain evidence.
