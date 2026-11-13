# Native feasibility before requirements review

## Implementation boundary

The candidate UI was deployed on 2026-11-13 at `a714767`; its authenticated
Mac-to-VM2 endpoint returned SONIC's retained deferral. Native planning is
implemented and tested locally, not production-commissioned.
The native planner is committed locally at Bulletproof
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

## Still required for commissioning

Deploy the coordinated worker/API/native source revisions through the approved
source-transition path. Then exercise the actual lease and receipt handoff before
claiming production closure. A coverage-infeasible candidate still needs a bounded,
independently reviewed successor; this change does not automatically rewrite its
window or weaken its scientific requirements. The broader general recovery loop
is intentionally deferred in Mission Control Notes and the Bible backlog.
