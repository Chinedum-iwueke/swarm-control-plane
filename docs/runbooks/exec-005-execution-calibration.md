# EXEC-005 execution-quality calibration runbook

## Production activation

1. Deploy migration `f6b2d8a47e50` and rebuild the API on VM2.
2. Produce a sealed native report from the matching Bulletproof source commit.
3. Run `worker/scripts/exec005_pilot.py` on VM1 with the operator environment.
4. Retain native and cross-repository reports with mode `0600`.
5. Confirm exact schema/receipt GET replay and `capital_or_order_authority: false`.

## Evidence response

Do not promote a calibration whose result selects `use_pessimistic_fallback`. Preserve
the sparse, censoring, unavailable or holdout-shift reasons, use the declared
pessimistic bound for research and schedule more prospective observations. Never turn
missing fills, timestamps or future-unavailable records into zeros.

## Rollback

Deactivate the calibration schema, pin the prior BT-005 model bundle, mark dependent
evidence superseded and retain all observations and receipts. A rollback may make an
execution estimate more conservative; it may never silently reduce modeled cost or
grant order authority.
