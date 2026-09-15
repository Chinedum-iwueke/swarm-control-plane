# Planner representation-aware intake correction

## Root cause and repair

The September 15 refreshed turns failed at conversational reasoning, before any
backtest. A read-only reproduction returned `compile_proposal` with nonempty
`unresolved_fields`. Those fields are reserved for `needs_clarification`.
The planner now states this invariant explicitly and permits one regeneration
with bounded, input-free validation feedback. A second invalid candidate fails
closed. Scientific blockers remain in interpretation; none are silently waived.

## Native representation evidence

Reuse Bulletproof commit `a7d8e112c21fe436ee2c5dc89e61614bcde28e10`,
`src/bt/data/resample.py`, SHA-256
`608d7460e6389e8f8e99c608b3a785cc4742a67376766d67578362b7d60cf886`.
Its supported targets are 1m, 3m, 5m, 15m, 30m, 1h, 4h and 1d, not 10m.
The native resampler emits complete UTC buckets only at rollover, labels their
start timestamp, suppresses incomplete buckets and does not invent missing bars.
Signal and execution clocks remain separate. Funding, OI, mark and index inputs
require independent point-in-time transformation specifications.

Grounding now retains registered dataset coverage, provider, instruments,
columns and transformations, plus the latest DATA-002 catalog partitions,
memberships and availability. Each catalog section is capped at 100 entries;
this is explicitly not an exhaustive filesystem inventory or access grant.
Reviewed resampling metadata is advisory, not an execution qualification receipt.

The inspected production snapshot admits a Bybit BTCUSDT 1m panel spanning
2021-01-01 through 2026-05-18, with 2,827,851 rows. Its memberships are empty.
This does not establish broad Binance/Bybit stable/volatile universe admission.
The current research mandate's one-month window does not meet the 365-day
founder-intake requirement. Missing equity inputs must not be substituted away.

## ML and RL boundary

Tier2A signal/state evidence can seed ML research but cannot become portfolio-PnL
evidence. ML-002 materializes causal features/labels and purged/embargoed splits in
Bulletproof; ML-001/003/004 bind model identity, evaluation, calibration and
abstention. A learned signal returns through the same backtest and promotion gates.
RL-001 requires sealed transition/reward/behavior-policy and action-support
evidence, using the DATA and prospective journal lineage. RL-002 evaluates
proposals conservatively off-policy. A signal episode alone is not an admissible
RL dataset. No registry automatically grants training, execution or capital authority.

## Verification and rollout

- Worker planner: 16 focused tests passed, including one-repair success and
  persistent-invalid failure with no execution authority.
- Full worker suite: 275 tests passed.
- Backend conversation: 7 focused tests passed, including catalog and native
  representation boundaries.
- Bulletproof native resampler/configuration: 9 tests passed.
- Changed Python files pass Ruff.
- Read-only live-task reasoning with the corrected prompt passed the typed
  reasoning contract, retained the original equity question and identified
  missing equity data and the mandate-window conflict.
- Full read-only reasoning-to-proposal replay using refreshed production catalog
  grounding passed the typed proposal contract. It preserved hourly BTC return-sign
  predictability, selected native closed 1h buckets from the admitted Bybit 1m
  panel, proposed two preregistered continuation/reversal variants and retained
  the 365-day/mandate-window and missing-membership blockers. No proposal was
  stored, materialized, approved or executed by this verification.

Production rollout and a fresh terminal cross-channel replay remain necessary.
Do not rewrite prior failed task contracts or represent local verification as a
completed production campaign. Rollback removes the new intake guidance and
bounded repair while preserving conversations, tasks and evidence.
