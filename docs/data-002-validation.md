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

Production acceptance completed on 2026-08-27 UTC:

- merged source commit: `24773719103fb99657a434db35c8be776e0478f2`
- VM2 migration head: `f3e8b2c61d90`
- rebuilt API: healthy, with snapshot register/list/get and resolution routes exposed
- prior catalog digest: `981c671b9959461804701c9b9661398b2b68b873f837f5762549f16a5ab233e4`
- current catalog digest: `3c5352526ef607d02502144cf8623dc53098322c4bf84f8395e0650384aa2e07`
- bound DATA-001 digest: `16c689717341872f0b15d0324122ddbc749d2174197d8f3f4ea7faadf75e3871`
- no-capital pilot: all eight catalog, replay and fail-closed checks passed
- retained evidence: `docs/evidence/data002-report.json`

The live proof grants no data-write, execution, order or capital authority.
