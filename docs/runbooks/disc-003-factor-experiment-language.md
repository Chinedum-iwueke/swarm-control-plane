# DISC-003 Representation and Factor Experiment Language

## Purpose

DISC-003 turns a registered hypothesis into a finite, inspectable experiment-language program. It does not execute trials, select winners, promote research, or hold capital authority.

## Contract

- Programs reference an existing hypothesis, immutable dataset-manifest digest, and BT-007 representation-contract digest.
- Features are closed expression trees. Arbitrary source code, imports, paths, network access, and dynamic evaluation are absent.
- Every field declares a unit, domain, observation clock, and availability lag.
- Feature reads require an effective lag of at least one decision interval. Forward observations exist only in the explicit evaluation label.
- Operators are allowlisted and unit checked. Expression depth is bounded.
- Parameter grids contain finite, distinct values and compile to no more than `maximum_trials` variants.
- Source, semantic, compiled, and per-trial digests make replay and duplicate detection machine-verifiable.
- Programs are immutable. A replacement explicitly supersedes one active program for the same hypothesis.

## Production Pilot

After deploying migration `e8a2b5c74d10`, run `worker/scripts/disc003_pilot.py` with retained hypothesis, dataset-manifest, and representation-contract digests. Success requires four deterministic variants, rejection of a current-bar feature, and `action_authority=false`.

## Rollback

Stop creating v1 programs and pin consumers to the last accepted compiled digest. Existing records remain retained for replay. Downgrade only when no program records need preservation.
