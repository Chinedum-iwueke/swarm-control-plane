# EXEC-009 validation

EXEC-009 adds the Hermes half of execution-degradation feedback without turning the
control plane into an execution analytics engine. The API registers one immutable
Bulletproof specification and accepts only the allowlisted native producer receipt
whose embedded specification digest matches an active registry record.

The focused contract suite covers immutable schema identity, digest drift, route
protection, producer authority and missing active-schema rejection. The native
Bulletproof suite separately covers point-in-time exclusion, identity collision,
single-breach noise resistance, consecutive strategy degradation, distinct venue and
infrastructure diagnoses, immediate outage handling, immutable incident digests and
the prohibition on automatic recovery.

The deterministic pilot must report all of these terminal decisions:

- healthy: `continue_monitoring`;
- confirmed strategy degradation: `shadow_fallback_review`;
- critical outage: `freeze_and_kill_review`;
- healthy evidence after kill: `independent_restore_review`.

All authority flags remain false. Live venue qualification remains pending deployment
of the dedicated eligible execution host and real EXEC-005/008 telemetry; fixture
evidence is never represented as venue continuity or production readiness.
