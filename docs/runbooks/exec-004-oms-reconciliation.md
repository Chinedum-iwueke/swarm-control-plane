# EXEC-004 OMS and reconciliation runbook

## Production activation

1. Deploy migration `e5a9c3f16d40` and rebuild the API on VM2.
2. Produce the sealed native report from the matching Bulletproof source commit.
3. Run `worker/scripts/exec004_pilot.py` on VM1 with the operator environment.
4. Retain the native and cross-repository reports with mode `0600`.
5. Confirm exact schema/receipt GET replay and `capital_or_order_authority: false`.

## Required response to ambiguity

When reconciliation returns `freeze_and_investigate`, stop all new submissions. Do not
retry an ambiguous command with another idempotency key. Capture a fresh independent
venue snapshot, compare canonical client order IDs, venue order IDs, fills, positions,
and balances, and preserve every discrepancy. Resume only after a new reconciliation
receipt reports zero material discrepancies and `submission_allowed: true`.

## Rollback

Deactivate the OMS schema, keep the quantitative receipt and all native evidence, and
leave submissions frozen. Downgrade the additive migration only after consumers no
longer reference the registry. Never rewrite or delete ambiguous order evidence.
