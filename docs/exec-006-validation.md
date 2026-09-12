# EXEC-006 validation

EXEC-006 keeps execution computation in Bulletproof and adds only immutable schema
registration and exact receipt custody to Hermes.

## Contract

- Producer: `bt.institutional.execution_scheduler.execution_schedule_receipt`
- Schema: `exec006-baseline-schedule-v1.0.0`
- Algorithms: market, limit, TWAP and causal-profile VWAP
- Dependencies: qualified EXEC-004 and EXEC-005 receipts at schedule creation
- Release: every proposed child order requires a fresh, exact RISK-005 receipt
- Authority: no allocation, capital, order or promotion authority

## Verification

- Bulletproof dependency suite: 57 tests passed.
- Hermes schema and receipt custody suite: 21 tests passed.
- Alembic: `f3c8d6a15e20` is the single head.
- Native replay: a four-child VWAP fixture is deterministic, retains pessimistic
  cost comparisons and stops at `propose_submit` without a RISK-005 authorization.

Production migration, schema activation and exact cross-repository replay are recorded
separately after deployment. The fixture is not evidence of a real candidate, fill,
venue submission or capital authority.
