# M11 Validation

## Scope

M11 establishes immutable research contracts and a trial-aware registry. It does not
enable unattended daily research, live trading, promotion, or sealed-holdout access.

## Implemented Controls

- Strict contracts reject unknown fields and invalid time ranges.
- Canonical SHA-256 digests bind every lineage transition.
- Hypotheses and experiments require independent exact-digest approval.
- Trial-family budgets count every attempt, including failures and negative results.
- One append-only result is retained for every registered trial.
- Result review must be independent from execution.
- PostgreSQL triggers reject update and delete operations for every registry table.
- Lineage retrieval exposes complete family counts and evidence chains.

## Validation State

Source contract tests completed on 2026-07-31:

- backend: `54 passed`;
- worker: `169 passed`;
- backend and worker compile checks passed;
- all M11-touched files pass Ruff;
- Alembic reports the single head `b2c4d6e8f110`.

A disposable PostgreSQL 17 rehearsal applied the complete migration chain to
`b2c4d6e8f110`. A source record was inserted and direct SQL `UPDATE` and `DELETE`
probes both failed with `research registry records are append-only`. The disposable
container was then stopped and removed.

VM2 migration and operational pilot completed on 2026-07-31. The pilot used a fresh
prospectively registered execution; it did not retrofit approval onto the prior M8
result.

The M11 pilot also refreshes the VM1 research role package to version `1.1.0`.
Canonical package serialization now includes the explicit empty runbook-package list;
the new digest must be registered and deployed rather than accepting the stale M8
attestation.

## Recommendation

## Operational Pilot

- hypothesis: `b74ff18a-7a64-404b-9e67-a32a0ddc2a6c`;
- hypothesis digest: `c4ecc90bd95010e3359c1993f99f86b96557077c974989618add652e76e998b9`;
- experiment: `833be54d-bc89-4969-97a0-344319e6cbd6`;
- manifest digest: `7dc489f42d1f0dfa45821c76bad2ae17473cad80534f32e2a1d4a8c31c64e9b6`;
- task: `7a4bd70b-9357-4381-adb7-6f78b494fb43`;
- reserved trial: `61ffa09d-7b5e-48d6-a650-e965c3a4fcce`;
- trial digest: `83b6bb83d2c793e98e8a0c87441df4ae086a50542e2ac119aea7f0ebbf11450b`;
- result digest: `defbb21580adaa8240d41af56b20dc284472c39dd9e180231cee0eb60501601f`;
- outcome: `accepted`, decision: `retain`, production eligible: no.

The event sequence was `task_created`, `task_approval_rearmed`, `task_leased`,
`task_started`, five heartbeats, and `task_completed`. Attempt count was one and every
execution event was attributed to `vm1-research-runner`. The registry contains one
trial in the family, hypothesis and experiment approvals by `research-governor`, and
an independent result review by `statistical-reviewer`.

The retained workspace is:

`/home/omenka/Projects/swarm-agent-workspaces/M11-RESEARCH-20260731T131414493757Z-7a4bd70b-9357-4381-adb7-6f78b494fb43/attempt-1`

Research evidence, audit, and report artifacts are mode `0600`. The
`bulletproof_bt` primary checkout contained unrelated local modifications when final
verification ran, so a clean-before/clean-after assertion is unavailable. Metadata
and artifact paths prove execution occurred in the isolated task worktree; the local
changes were neither reverted nor attributed to the worker.

## Defects Resolved During Pilot

- Lease selection now skips stale approval records rather than blocking the queue.
- Idle lease polls persist approval-expiry reconciliation.
- Expired digest-bound tasks have an audited approval-rearm operation.
- The research package was advanced to `1.1.0` rather than accepting a stale
  canonical attestation.

## Recommendation

**Go for M12 and additional supervised registered trials.** No-go remains for daily
unattended research, live trading, or promotion. Those require retrieval evaluation,
separate research roles, sealed-holdout controls, and the later M13/M14 gates.
