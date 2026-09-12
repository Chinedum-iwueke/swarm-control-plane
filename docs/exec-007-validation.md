# EXEC-007 validation

EXEC-007 keeps runtime safety computation and enforcement in Bulletproof. Hermes
registers the immutable safety schema, validates the authoritative producer, and
retains the exact qualification receipt.

The local state begins frozen. Freeze and kill transitions are durable, hash chained,
idempotent and do not call Hermes or an exchange before containment. Missing, corrupt
or divergent state blocks new orders. Cancellations remain available while contained;
position reduction additionally requires explicit emergency-reduction authority.

Recovery requires all of the following:

1. An exact qualified EXEC-004 receipt whose reconciliation permits submission.
2. A fresh Hermes GOV-001 `execution-recovery/resume` decision bound to the current
   safety-state digest and the human actor.
3. An explicit `bt-exec-safety recover` command.
4. Normal live startup reconciliation and per-order RISK-005 authorization afterward.

Restart is not recovery. A `reconcile_only`, incomplete or corrupt prior state blocks
live startup. Rollback leaves the state frozen and disables EXEC-007 receipt admission;
it never initializes a runtime as ready.

The deterministic qualification pilot exercises partition, corrupt-state, runaway-order
and human-recovery paths without venue credentials, orders or capital. DEMO-001 must
separately qualify real demo-venue behavior.
