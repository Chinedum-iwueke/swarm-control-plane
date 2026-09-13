# EXEC-011 Venue Telemetry Publication

## Ownership

Bulletproof is the sole producer of normalized execution state and trade episodes.
The control plane verifies and retains its receipt and sanitized projection. Mission
Control reads that projection without receiving credentials or raw private payloads.

## Deployment

1. Deploy Alembic revision `e8b4c2d60f31` and rebuild the API.
2. Generate the native Bulletproof report with `scripts/exec011_pilot.py`.
3. On VM1, run `worker/scripts/exec011_pilot.py` with the native report.
4. Reinstall Mission Control and open `?view=execution`.

The publication order is schema, exact quantitative receipt, sanitized replay, exact
replay read, then environment-filtered overview. Every write is idempotent by digest.

## Failure And Rollback

- A missing schema or producer receipt blocks projection publication.
- A digest, identity, or secret-policy mismatch returns conflict and writes nothing.
- Sequence gaps, incidents, and REST/stream disagreement remain visible as degraded.
- Rollback freezes venue collection, preserves the append-only journal and receipts,
  and removes only the Mission Control reader/API deployment if required.

No step grants order, capital, allocation, or promotion authority.
