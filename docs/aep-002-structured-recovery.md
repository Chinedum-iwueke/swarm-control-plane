# AEP-002: structured findings and idempotent recovery

Implementation complete; not deployed or end-to-end certified by this document.
Extends existing requirements recovery rather than creating another scheduler.

## Contracts and ownership

`RecoveryFinding` in `backend/app/schemas/recovery_finding.py` binds an obligation
to its rejection subject, exact evidence digest, requirement reference, owning
stage, severity, permitted changes, verification steps and recovery condition.
Scientific approval and execution authority are always false.

`correction_worklist` retains its existing v1 fields and adds typed findings and
finding digests. Duplicate obligations normalize deterministically. Raw reviewer
prose is retained as an obligation requiring diagnosis, not a proven claim of
infeasibility. The requirement reference names the review obligation; it does not
pretend that prose identified an exact underlying specification clause.

Requirements-review obligations belong initially to method design. Diagnosis
can later establish a more specific cause; this increment does not invent that
diagnosis or implement the AEP-004 reasoning episode. A changed subject produces
different finding/worklist digests. Old worklists are not rewritten.

`RequirementsDisposition` now records owning stage, with a compatible default for
old documents. Known machine reasons retain the six existing dispositions.
Unknown or mixed feasibility reasons require triage and do not authorize automatic
repair. Native insufficient-history, support and composed-warmup codes remain
distinct. Waiting for existing review/native tasks does not schedule another repair.

## Durable recovery ledger

The existing immutable `requirements_disposition_recorded` events are the ledger.
The parent mandate row is locked before checking/inserting a decision. Pending
events are flushed before duplicate lookup, including repeated calls in one
transaction with autoflush disabled. Changed evidence creates a new linked entry.

Correction scheduling locks and refreshes the mandate before inspecting current
status/budgets, preserving already-pending transaction changes with a flush.
Its existing candidate/rejection/mandate fingerprint still prevents unchanged
completed or failed seeds from being scheduled twice. A new mandate is new
authority, not evidence that an old defect was repaired; depth limits still apply.
No loop resets counters, edits history, grants capital or overrides review.

## Verification

- Tests cover typed obligations, duplicate normalization, source-subject changes,
  unknown-code triage, historical disposition reads, stale mandate state and
  existing authority/lineage gates.
- A disposable PostgreSQL test starts two concurrent sessions and delivers the
  same decision twice in each transaction: exactly one event remains. Changed
  evidence produces the next hash-linked event. This test is wired into CI.
- Focused campaign/discovery/handoff regression suites are run with a dummy local
  secret-file setting; no production database or model call is required.

This is infrastructure correctness evidence, not measured autonomous scientific
recovery. Diagnosis quality, general method correction and live handoff remain
AEP-003 through AEP-008. AEP-001 provisional labels are not quietly converted to
ground truth by these tests.
