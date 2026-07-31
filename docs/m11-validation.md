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

VM2 migration and operational pilot remain pending deployment of the reviewed commit. The
pilot must use real M8 task and artifact evidence; synthetic registry evidence is not
acceptable.

The M11 pilot also refreshes the VM1 research role package to version `1.1.0`.
Canonical package serialization now includes the explicit empty runbook-package list;
the new digest must be registered and deployed rather than accepting the stale M8
attestation.

## Recommendation

No-go for daily autonomous research until the VM2 migration, real one-trial pilot,
database immutability probe, and independent lineage verification pass. M11 source
completion alone does not grant execution or promotion authority.
