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

Production acceptance completed on VM2 after implementation merge
`51910ac91b7b472a553187450b22a1045023920f` and pilot correction merge
`5c324c7c3f041032ad2222c75224ff31cd6721a0`:

- Alembic migration `a4f9c3d72e10` was at head.
- The rebuilt API was healthy and exposed admission, event, publication-disable,
  publication-restore and snapshot routes.
- Snapshot `0acbf36c-29d4-427d-a83b-f943b004d3ba` bound catalog digest
  `3c5352526ef607d02502144cf8623dc53098322c4bf84f8395e0650384aa2e07`.
- The pilot passed all nine checks and retained six append-only events.
- The retained report is `docs/evidence/data003-report.json`, with SHA-256
  `1ff45b5f0bd20f7a1a9d291c37c9e185a3623ee325422a89ab9bdcdf646f75b9`.
- The pilot held neither source-write authority nor capital or order authority.
