# PORT-004 capacity and liquidity runbook

1. Produce the native report from the merged Bulletproof PORT-004 implementation.
2. Deploy the Hermes migration and rebuilt API.
3. Run `worker/scripts/port004_pilot.py` with the root-owned operator environment.
4. Verify exact schema, receipt and capacity digests and retain the root-only report.

Rollback deactivates admission of the affected schema version and restores the prior
conservative portfolio cap. Immutable native and Hermes receipts remain retained.
Missing, stale or unmatched evidence must continue to yield zero supported notional.
