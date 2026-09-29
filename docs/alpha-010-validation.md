# ALPHA-010 Validation

Status: source producer, scheduling seam and canonical utilization telemetry implemented;
production activation and observed closure remain open.

- Deterministic resource planning uses CPU, available RAM, a free-memory floor and
  measured per-worker estimate; it never allocates from CPU count alone.
- With the current VM1 observation, two approved jobs receive six workers each. A
  synthetic 24-worker host permits three eight-worker jobs.
- Unapproved execution, new code, capital/order work and sealed-OOS research are
  rejected explicitly.
- An empty backtest queue falls through to eligible native signal, representation,
  evidence or held-out skill work; a completely empty eligible queue is visible.
- External evidence requires public unauthenticated HTTPS and exact host allowlisting.
  Social evidence remains observation-only and instruction-like text is quarantined.
- Skill changes require source traces, held-out replay, an independent evaluator,
  unchanged authority and no regression; success stages rather than adopts.
- Bulletproof PR 353 adds the native DISC-010 receipt producer, content-bound runner,
  lower-priority global-capacity queue adapter and manifest-only replenisher.
- Thirty-eight native tests cover cross-asset discovery, deterministic null retention,
  incomplete-bar exclusion, fractional-difference drift, sealed-OOS invariance,
  1-versus-8-worker receipt parity, queue priority/deduplication and replenishment.
- A committed-CLI smoke run produced a cross-asset receipt with one injected question
  candidate and `final_oos_opened=false`; this is synthetic functional evidence, not an
  alpha or profitability claim.
- Hermes validates DISC-010 producer identity, full trial/candidate accounting and the
  closed strategy/promotion/execution authority boundary before registration.
- Every registered trial retains its exact contract and must replay to the bound trial
  digest. The VM1 publication bridge is idempotent across local-state loss and publishes
  only complete canonical receipts.
- Registered survivor, null and invalid trials enter the next ALPHA-004 context; Mission
  Control renders the canonical ledger without implying OOS or promotion authority.
- A root-only publisher projects the read-only native SQLite queue and scheduler state
  into immutable Hermes utilization snapshots every two minutes. It accounts exactly
  for pending, locked, done and failed governed assignments and signal screens.
- Mission Control distinguishes approved backtests, fallback discovery, queued work,
  resource blocking, stale telemetry and a genuinely empty eligible queue. Three
  consecutive empty, stalled or blocked observations create a Telegram founder alert.

Focused source verification covers policy, receipt validation, publication replay,
capacity accounting, systemd hardening, discovery-context projection, Mission Control
and native Bulletproof behavior; Ruff and JavaScript syntax checks pass. The production
services and schema from this change remain undeployed until the pinned rollout is run.
No model, order, promotion or capital authority was changed.

RI-017's public-feed worker can consume otherwise idle network/retrieval capacity but is
not a substitute for the native quantitative queue. It has no scientific, execution or
capital authority and enters ALPHA-004 only as sanitized question-seed metadata.
