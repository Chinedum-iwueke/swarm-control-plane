# RISK-005 real-time deterministic risk

## Deploy

Apply migration `e2b7c5f94d10`, rebuild the API, then register the exact Bulletproof
`REALTIME_RISK_SPECIFICATION` under producer
`bt.institutional.realtime_risk.realtime_risk_decision_receipt`.

## Monitor

Track decision latency, denial reasons, snapshot age, state-version conflicts, and
submission-gate failures. A missing or stale receipt is an expected fail-closed outcome,
not permission to bypass the gate.

## Incident response

1. Freeze new exposure independently.
2. Cancel open orders through the OMS reconciliation path.
3. Permit a close only when the decision is `reduce_only_exit` and the bound order
   actually reduces the current position.
4. Reconcile venue and local state, increment the state version, and obtain a new
   RISK-005 receipt before resuming.

## Rollback

Mark the schema inactive and keep external order submission disabled. Do not roll back
to an ungoverned risk path. The emergency freeze/cancel mechanism remains independent.
