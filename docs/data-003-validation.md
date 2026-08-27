# DATA-003 Validation

## Contract evidence

- Immutable governance snapshots bind exact DATA-002 catalog digests.
- Quality, lineage, entitlement, capacity, retention and recovery evidence is metadata only.
- Unknown principals and undeclared purposes/actions are denied by default.
- Corrupt, stale or capacity-exhausted partitions fail admission.
- Retention holds block deletion without blocking governed reads.
- Derived publication disable and verified restore are append-only events.
- Protected source payload is forbidden by strict schemas.
- Source partitions remain immutable and read-only.

## Automated evidence

Tests cover corruption, duplicates, gaps, staleness, entitlement denial, capacity warning
and exhaustion, retention holds, invalid lineage, unknown recovery objects, unverified
restore, protected-payload rejection, event visibility and route registration.

## Production acceptance

Production completion requires migration `a4f9c3d72e10` at head, a healthy rebuilt VM2
API exposing all lake-operation routes, and a successful no-capital live pilot against
the production DATA-002 catalog.
