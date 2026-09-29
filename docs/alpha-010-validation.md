# ALPHA-010 Validation

Status: source producer and scheduling seam implemented; production activation open.

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

Focused source verification: 17 policy tests, 47 receipt/external-evidence tests and 38
native Bulletproof tests passed; Ruff passed. No production service has been installed
and no real-lake DISC-010 receipt has yet been registered. No network, model, order,
promotion or capital authority was changed.
