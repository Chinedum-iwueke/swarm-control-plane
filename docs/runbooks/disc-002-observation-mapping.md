# DISC-002 Observation, Anomaly and Opportunity Mapping

## Purpose

Convert governed DISC-001 questions and RI-004 evidence into immutable typed maps while
preserving the distinction between observation, anomaly, mechanism and investable
opportunity.

## Evidence ladder

1. `observation` records population, baseline, estimate, uncertainty, regime controls
   and evidence.
2. `anomaly` additionally requires a passed null control.
3. `mechanism` additionally requires a causal story, rival explanations and explicit
   falsification criteria.
4. `opportunity` additionally requires at least two independent evidence objects, a
   non-zero incremental effect and reconciled positive net effect after transaction,
   financing and impact costs.

An anomaly is not an opportunity. Noise, failed nulls, cost-erased effects and missing
incremental evidence fail closed.

## Operations

- Register only canonical, digest-matching documents.
- Treat semantic duplicates as conflicts rather than additional discoveries.
- Replace a map only by registering a new revision with `supersedes_map_id`.
- Retain registration and supersession in the digest-chained event ledger.
- Never include protected market payload, credentials or unrestricted source text.

Rollback means superseding the affected map with a corrected or rejection map. It
does not delete prior evidence or grant execution, order or capital authority.
