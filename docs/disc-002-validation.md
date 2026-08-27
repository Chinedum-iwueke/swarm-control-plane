# DISC-002 Validation

## Contract evidence

- Observation, anomaly, mechanism and opportunity are distinct typed stages.
- Population, baseline, effect, uncertainty, regime controls and evidence are required.
- Null controls gate anomaly classification.
- Mechanism, rivals and falsification gate mechanism classification.
- Independent incremental evidence and reconciled positive post-cost effect gate
  opportunity classification.
- Semantic duplicates fail closed and revisions use immutable supersession.
- Protected market payload is excluded by strict schemas.

## Automated evidence

Tests cover noise/null omission, semantic duplicates, regime-control requirements,
cost-erased effects, insufficient independent evidence, digest mismatch, protected
payload, immutable supersession and route registration.

## Production acceptance

Production acceptance completed on VM2 after implementation merge
`226bdfbc9e18c3198c4b80528544694b964fb727` and pilot contract correction merge
`8846faee68c8433a14468df344a2a80c982da409`:

- Alembic migration `b5d8e2f41a70` was at head.
- The rebuilt API was healthy and exposed map registration, replay and event routes.
- The pilot bound a real DISC-001 cycle, successful DATA-003 admission event and two
  independently produced canonical evidence objects.
- A cost-erased candidate failed admission; qualified opportunity map
  `358f8ec0-700e-4c39-af52-b2515b54cf7c` was registered and then superseded without
  deleting its event chain.
- The retained report is `docs/evidence/disc002-report.json`, with SHA-256
  `e83b15d909782c5810432277b1c3cb91789e9faf5168a6bf8b51ea1b5fb9cb2c`.
- The service held no source-write, execution, order or capital authority.
