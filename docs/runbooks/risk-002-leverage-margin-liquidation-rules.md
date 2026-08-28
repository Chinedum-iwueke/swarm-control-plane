# RISK-002 leverage, margin, liquidation and rules runbook

1. Resolve the exact DATA-001 venue, instrument, listing, increments, and snapshot digest.
2. Require a current admissible RISK-001 dossier.
3. Capture the venue rule source, source digest, dual clocks, lifecycle transition, contiguous margin tiers, price/funding limits, and liquidation buffer.
4. Bind a position-state digest and register the request. The server derives the allow/deny receipt.
5. Replay by evaluation ID and verify the receipt digest before any downstream sizing work.

Rollback marks the affected rule pack suspended or retired and denies the venue/instrument. It never silently restores stale limits. This service does not submit orders or allocate capital.
