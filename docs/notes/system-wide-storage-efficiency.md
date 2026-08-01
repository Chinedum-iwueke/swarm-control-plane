# System-Wide Storage Efficiency

## Note

- Status: source note recorded; governed M14C record will be explicitly deferred for
  30 days pending a bounded measurement and restore-drill proposal
- Recorded during: M14B Research Intelligence Director
- Affected system: `bulletproof_bt` research memory on VM1
- Proposed owner: Operational Memory Steward
- Urgency: investigate before unattended daily research materially increases volume
- Execution authority: none; this note does not authorize cleanup or schema changes

## Observation

The authoritative SQLite database at
`bulletproof_bt/research_db/research.sqlite` was approximately 27.7 GB during the
M14B bridge validation. The read-only export observed:

- 4,276,813 research-memory trade rows;
- 541,739 invalid trade rows;
- 13,522 state buckets;
- 11 candidate records;
- 16,690 recommendation records.

The volume appears high relative to the known number of completed experiments. This
is an observation, not yet a diagnosis. No records were deleted or modified.

## Audit Questions

1. Are identical trades or recommendations ingested more than once across reruns?
2. Does `UNIQUE(experiment_root, run_id, source_trade_id)` prevent the actual retry
   and path variants produced by the orchestrator?
3. Are raw JSON, derived columns, indexes, SQLite free pages, WAL files, or temporary
   artifacts responsible for most of the footprint?
4. Which evidence must remain row-level, and which can be compacted into immutable
   partitioned artifacts plus bounded aggregates?
5. What retention and storage budgets should apply to VM1 workspaces, artifacts,
   knowledge chunks, control-plane events, backups, and research memory?
6. Can compaction preserve exact trial reproduction, rejected evidence, provenance,
   and digest verification?

## Required Evidence Before Remediation

- SQLite page, table, index, and free-page measurements;
- duplicate analysis by experiment, run, source trade, and content digest;
- growth per completed research run;
- backup and restore measurements;
- a rehearsed migration and rollback plan;
- proof that retained trials reproduce before and after compaction.

## Safety Boundary

Do not run `VACUUM`, delete rows, rewrite research artifacts, or change retention
until a bounded audit task is approved and a backup plus restore drill succeeds.
