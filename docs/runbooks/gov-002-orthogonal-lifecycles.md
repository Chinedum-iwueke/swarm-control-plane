# GOV-002 orthogonal lifecycle operations

## Invariant

Research validity, evidence admissibility, operational eligibility and capital
authority are different facts. A favorable result cannot promote itself by causing a
state change in another dimension.

```text
research:   proposed -> registered -> running -> succeeded | failed
evidence:   unassessed -> admissible | disputed | invalid -> retracted | retired
operations: not-considered -> candidate -> approved -> shadow -> demo -> live
capital:    no-authority -> eligible -> allocated -> reduced | revoked
```

Arrows in different rows are never automatic. Cross-row conditions are prerequisites
checked when an explicit command arrives.

## Deployment

1. Deploy migration `f7c2a9d41e80` and rebuild the VM2 API.
2. Reinstall Mission Control on the Mac.
3. From VM1, source `pilot-operator.env` and run
   `worker/scripts/gov002_pilot.py`.
4. Retain the pilot dossier and query the same subject from a fresh client.
5. Confirm Mission Control shows four independent states and capital remains
   `no-authority`.

## Concurrency and replay

Clients submit a unique command ID and the expected projection version. The server
locks the selected projection; a stale writer receives `409` with the current version.
Reusing a command ID with changed dimension, command or version is rejected. Events
carry the previous event digest, and dossier reads replay each dimension from its
initial state before returning the current projection.

## Rollback

The tables are additive. Restore the prior API to stop accepting GOV-002 commands
while retaining projections, authority decisions and events. A compatible projector
can rebuild current state from the retained chain. Do not downgrade the migration
after canonical GOV-002 events exist unless those events have been exported and the
feature is being abandoned.
