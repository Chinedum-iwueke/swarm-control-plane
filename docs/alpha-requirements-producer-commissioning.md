# Requirements producer commissioning

## 2026-11-13 checkpoint: not certified

Representation output now proposes typed scientific requirements separately from
its transformation graph: research-bar clock, feature warmup, training,
validation/test support, horizon/purge/embargo, scientific duration, bounded smoke
and named event support. These proposals have no approval or coverage authority.
The controller retains the proposal and a basis digest with the candidate. Old
candidates without requirements retain their historical document shape.

New selected-panel admission tasks can carry the frozen representation and the
mandate's exact window. Bulletproof produces `predictor_coverage_evidence` from
verified recovery-copy bytes, finite required OHLCV values, complete source bars,
basket alignment and finite representation outputs. The initial probe used a
two-million source-row read budget. Admission now uses bounded 100,000-source-row
chunks and an independent retained-research-row limit. It neither scans
the full lake nor starts model inference. Non-OHLCV fields fail closed pending
field-specific availability verification.

The requirements handoff now validates the native admission task's retained
coverage result against the candidate, representation, final compact DATA
bindings, source commit, interval count and approved historical envelope. It
publishes a hash-linked campaign event and routes independent spec and causality
reviews before creating an engineering task. Pending or rejected review cannot
release paid authoring. Reconciliation reuses the publication and route.

Predictor coverage explicitly does not certify point-in-time membership. The
review scope is fixed-basket predictor availability; reviewers must reject
unsupported universe or event-support claims. Publication is not certification.
Legacy candidates missing scientific requirements stop at
`propose_scientific_requirements`, without guessing support from source-row counts.

`alpha004_mandate.py --commissioning` proposes three cycles, three hypotheses,
24 trials, at most two candidates per cycle and two concurrent campaigns. It
does not approve the mandate. Catalogue authority supports up to 4096 instruments
without changing the 128-asset representation basket limit. The execution-worker
contract still caps baskets at 20; larger-basket execution remains unqualified.

## Read-only genuine candidate probes

No tasks, approvals, campaign states or backtests were created by these probes.
The reports are local protected artifacts under
`~/.local/state/invariance-swarm/coverage-probe-20261113/`, not Git-tracked outputs.

| Source task | Basket | Finite research decisions | Usable interval |
| --- | --- | --- | --- |
| 5cac48da-c13b-4d41-9b4f-96c1cf5aa409 | TRBUSDT, 20m | 26122 | 2025-08-08 21:00 UTC to 2026-08-06 16:20 UTC, half-open decision grid |
| 2329a95c-e9e6-446b-87f7-03f2bccd1dae | XTZUSDT, RENDERUSDT, BTCUSDT, 15m | 27066 | 2025-08-09 20:30 UTC to 2026-05-18 19:00 UTC, half-open decision grid |

Evidence digests:

- TRB: `f943932c9ba15cd2b519df1e4377c2dfe752bdf537b30716fb8988bd8c85b902`.
- Basket: `89cfd1db25cc12e8130c97d866408addb4a64bb4b9fa1dadd9846a912d256d63`.

Both frozen tasks request 2025-08-08 20:14 UTC through 2026-08-08 20:14 UTC,
but their actual available data does not cover that whole year. Metadata of the
current canonical panels agrees with the frozen copies: TRB ends August 6,
XTZ August 8, RENDER August 4, and BTC May 18, 2026. No latest-data coverage was
invented and no original task or dataset digest was rewritten.

## Remaining certification gates

1. Independently review the explicit requirements against the frozen estimand.
2. Verify point-in-time membership and any non-OHLCV field availability.
3. Distinguish source-clock coverage usable for warmup from finite-feature coverage
   so the planner does not accidentally charge transformation warmup twice.
4. Authorize successor windows/bindings with enough common history, or admit newer
   data. Preserve parent lineage and exact source commits; do not edit old tasks.
5. Bind final registry identities to verified coverage and requirements, then carry
   both smoke and scientific plans through qualification and execution.
6. Only then launch the two bounded real authoring successors, independent review,
   smoke and one-year BT-009, publication and memory. No full queue restart yet.

The founder task delegation was verified at this checkpoint, expiring at
2026-11-13 18:37:52 UTC. It does not grant weekly-mandate approval.

The new handoff has offline custody, mutation, rejection, pending-review,
approval and repeated-reconciliation tests. The exposure producer now snapshots
bounded same-question/source-candidate governed task history, conservatively
excludes attempted execution windows, and rejects in-flight work, unknown windows
or scientific attempts lacking retained contracts. It retains prior published
successor lineage and rechecks exposure before successor publication/materialization.
This scope is not a claim about research performed outside the governed system.

Real routed review receipts and the full native execution path remain
commissioning work; neither is inferred from passing unit tests. The previous canonical mandate is
completed at 42 cycles. No old engineering task was restarted by this repair.

Further static tracing found two downstream boundaries to validate before claiming
completion: execution assignments must retain native smoke/scientific plans, and
successful engineering currently advertises
`founder_merge_strategy_and_rebind_source_commit`. Neither a running service nor
an authoring success proves those subsequent transitions have occurred.

## Mission Control deployment

The catalogue retirement audit was pushed to main as `9234cb4`. The Mac rollout
also exposed an existing Python 3.9 event-loop binding failure in the overview
poller. `2172e3d` creates its synchronization primitives on the serving loop and
adds a construct-before-loop/restart regression. The focused broker suite passes.
The wider Mission Control suite has one pre-existing static asset budget failure:
`app.js` is 352574 bytes against its 350000-byte cap; 189 tests pass. The cap was
not raised to hide the failure.
