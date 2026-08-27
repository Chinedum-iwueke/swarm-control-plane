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

Production completion requires migration `b5d8e2f41a70` at head, a healthy rebuilt VM2
API exposing map and event routes, and a live no-capital pilot that retains an
observation, rejects a cost-erased opportunity, registers a qualified opportunity and
supersedes it without deleting evidence.
