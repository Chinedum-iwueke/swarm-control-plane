# Native feasibility before requirements review

## Implementation boundary

The candidate UI was deployed on 2026-11-13 at `a714767`; its authenticated
Mac-to-VM2 endpoint returned SONIC's retained deferral. Native planning is now
deployed with a live planning-only infeasible-input commissioning receipt.
The ready-input to independent-review path is not yet production-certified.
The native planner is published at Bulletproof
`a5ed7a241e21b2aabfe6f1be90e7d97a2d4f5f81`, containing
`scripts/plan_alpha_requirements.py`. Existing candidates pinned to
`d951b6fd58e688f4adc5d75c74bfedcc86bce1f1` must not silently switch revisions.

## Order and economics

1. Validate native admission custody and exact representation coverage.
2. Queue one content-addressed, risk-zero native planning task using the existing
   admission worker. It reads retained coverage, not the lake, and calls no LLM.
3. Compute composed feature history and separate smoke/scientific partitions.
   Preserve support minima, purge/embargo, target tails, compute bounds and source.
4. Retain infeasibility as a candidate deferral with zero trials. A runtime failure
   is a distinct blocker. Neither creates an independent review or blindly retries.
5. Only ready, digest-bound native evidence reaches the two independent reviewers.
   Review publications are reused when their subject and evidence are unchanged.
6. Successful review returns a native receipt reference with reviewed requirements.
   It does not certify event support, a strategy, a backtest or capital authority.

Structural lookback is a lower bound, not proof that all feature values exist.
For example, returns followed by a six-bar rolling statistic lagged six bars
need 12 prior bars. Zero denominators, gaps and actual event counts still require
their own validity checks. Contradictory prose remains an independent semantic
review concern; the planner does not reinterpret the research question.

## Candidate visibility

Research's **Deferred & Blocked** view reads retained deferred attempts and
current blocked campaign candidates through a bounded, searchable API. It shows
the question, blocker, missing evidence, classified responsible component,
reconsideration conditions and retained evidence. Unknown ownership stays unknown.
Historical deferrals are explicitly labeled; they do not assert that no successor
exists. There is no bypass-review retry button.

## Verification

- Read-only production projection returned 40 dispositions, including retained
  SONIC and current SPX/BTC, without changing campaign state.
- Local replay of SPX/BTC's retained inputs: smoke ready (138 bars required),
  science deferred (2,214 required, 1,697 available, 517 short). The composed
  lookback and declared warm-up both equal 12. This is not a production receipt.
- Regression tests cover no-review-on-infeasibility, immutable task reuse,
  changed evidence rejection, smoke/scientific separation and composed history.
- Browser fixture checks cover desktop/mobile layout, escaped content, filters,
  pagination, retained expansion and explicit stale/error state.

## Live source transition and handoff: 2026-11-13

The founder explicitly authorized the native-planner source transition and
no-capital live handoff validation. VM1 admission worker and VM2 API/directors
were updated to the gate implementation (`d8e4117`). Runtime image parity and
API health were verified. No historical campaign or mandate pin was rewritten.

`worker/scripts/commission_native_feasibility.py` creates a bounded, parent-linked,
planning-only successor using retained admission/review evidence. It does not
read the lake, execute a strategy, issue scientific authority or call a model.

- Parent admission: `c7f0b28f-767a-41a5-8497-416d5b1af88a` at `d951b6f`.
- Live task: `68a3b0d7-e704-41fd-9722-fdfdfc71218e` at `a5ed7a2`.
- Native receipt: `2783dec22ccbbcde63483866dad134d0f0f888c22ef570f655bd02d8a8fe5f66`.
- Real worker lease, start and completion; one attempt, 1.4006 seconds.
- Native status `deferred`: smoke ready, scientific coverage 517 bars short.
- Control-plane receipt validation and lease-time producer custody passed.
- Repeated commissioning reused the same completed task; no extra attempt.
- Scientific requirements, original window and parent evidence remained unchanged.

The negative path is demonstrated at the native producer/receipt boundary, not
an autonomous campaign success or an approved scientific result. The commissioning
task itself did not materialize independent review; service regression tests cover
the no-review-on-infeasibility branch. A ready candidate still needs to demonstrate
the actual campaign-to-review route in production.

## Remaining boundary

A coverage-infeasible candidate now receives an outcome-blind successor proposal
before paid review when its mandate supplies a bounded historical envelope and
the complete governed exposure ledger. The original report remains deferred.
Both successor plans must be ready; both reviewers assess the proposal and the
unchanged requirements together. Only their approval releases the new engineering
window. Original candidate, admission and rejection records are not rewritten.

Working-tree replay of retained SPX/BTC evidence selected May 14, 2025 through
May 18, 2026, including explicit warmup, split gaps and target tail. Both smoke
and scientific plans were ready and the control-plane validator accepted their
bindings. This is an offline contract check, not a new production receipt or a
scientific result. Production review, engineering and BT-009 remain to be proved.
The broader general recovery loop remains deferred in Notes and the Bible backlog.
