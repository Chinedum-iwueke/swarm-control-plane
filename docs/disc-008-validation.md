# DISC-008 Validation

## Production evidence

- Implementation PR: #175; deployed commit `110af2b9104dd3502987af94776916cdd849e5d2`.
- VM2 migration: `b1d5e8f20a40`; API health: healthy.
- Live session: `be033159-bc20-4c82-b81f-fbf016027033`.
- Task graph: `4eaa1e3e-179a-49b7-91f9-11ebd2772a64`; digest `30868075b09bfd97f88121e349088b9f7c5611ceda8d91999ba6a435dc520fe5`.
- Agenda digest: `9ebb310edac8a9acbfe67d048c0bcb03abad3a062bce9ddd51b9722e9376c161`.
- Budget digest: `7e32e5da9faea51d46bf6656597c7ff39d0eec9ec7a5ea81b3ea4cce6df04e13`.
- Retained outcomes: negative, failed and invalid.
- AGT-006 receipt: `153cf0ea907329c97aaf5728507dc3806b42548b94e4d213acde032b47683104`.
- DISC-007 audit: `f8bf5a21bf539e0b4e46cf4b54405d0cd4e0fcaa9d0a1c47950d43ec487dd62f`.
- Report digest: `bbb435dc574af12c351591d96fc9deab8b379908f8df6079f0060ad8bc601c1e`.
- Validation: 528 backend tests and 14 focused tests passed; Ruff clean.
- Canonical report: `docs/evidence/disc008-report.json`.

## Invariants

- Exact agenda-to-task-graph binding and explicit no-capital authority.
- Fixed task, attempt, duration, reconciliation, stall and worker-loss budgets.
- Digest-chained session registration, checkpoint, progress, escalation and closeout events.
- Scope drift, conflict, no progress, worker loss and task-graph failure fail closed.
- Graph success remains `awaiting_closeout` until AGT-006 and DISC-007 evidence is bound.
- Operator cancellation cancels remaining graph work without deleting outcomes.
- No approval, scope expansion, promotion, order or capital authority.
