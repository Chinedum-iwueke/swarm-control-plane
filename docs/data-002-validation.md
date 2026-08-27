# DATA-002 Validation

## Contract evidence

- Catalog and partition content is immutable and SHA-256 bound.
- Every partition is read-only and tied to an exact DATA-001 identity snapshot.
- Event, observation and availability clocks remain separate and timezone aware.
- Corrections retain ordered ancestry; consumers select the latest revision known at
  their cutoff, not today's revision.
- Membership and source availability are point-in-time records.
- Gaps, ambiguity, unavailable sources, identity conflicts and lookahead fail closed.
- Rollback pins a prior catalog digest and never mutates history.
- No order or capital authority is present.

## Automated evidence

The targeted suite covers original/corrected replay, gaps, duplicates, correction
ancestry, membership drift, source delay, timezone-naive clocks, ambiguous overlap,
read-only enforcement, closed DATA-001 identity binding and routes.

## Production acceptance

Production completion requires migration `f3e8b2c61d90` at head, a healthy rebuilt VM2
API, all catalog routes in live OpenAPI, and a successful digest-bound no-capital pilot.
