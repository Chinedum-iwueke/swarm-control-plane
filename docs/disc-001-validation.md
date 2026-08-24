# DISC-001 Validation

## Boundary

The daily research director selects and ranks questions. It does not approve a
question, create an executable trial, grant a worker lease, or authorize capital.
Founder approval emits a `task_ready` event whose next step is hypothesis-brief
compilation under a separate execution approval.

## Implemented contract

- Approved Research Intelligence surveillance dispositions are the primary candidate
  source; deterministic program mandates remain the fallback.
- Ranking binds priority, novelty, evidence quality, freshness and prior-question
  similarity. Retracted, stale, previously selected and near-duplicate candidates are
  excluded.
- Weekly program budgets remain authoritative.
- Each cycle retains publication, routing-event, citation, ranking and question
  digests.
- Proposal, decision and task-readiness events are append-only and digest-bound.
- Founder decisions use optimistic concurrency against the exact question digest.
- Mission Control displays provenance and ranking and provides explicit Approve and
  Reject actions.

## Verification

Run:

```bash
POSTGRES_PASSWORD_FILE=/etc/hostname PYTHONPATH=backend \
  .venv/bin/pytest -q backend/tests/test_daily_research.py
PYTHONPATH=mission-control/src .venv/bin/pytest -q mission-control/tests
.venv/bin/ruff check backend mission-control/src mission-control/tests \
  worker/scripts/disc001_pilot.py
node --check mission-control/src/hermes_mission_control/static/app.js
```

The focused director suite covers deterministic novelty ties, stale and retracted
evidence, semantic duplicate families, budget exhaustion, fallback behavior, approval
events and decision races. The Mission Control suite covers the authenticated,
digest-bound decision transport.

## Live replay

After applying migration `a8c4e1d72b90`, run the pilot first without `--approve` to
inspect the selected question. Run it with `--approve` only after founder review. The
result is a mode-0600 report containing the complete selection and event digest trail.

## Rollback

Disable director selection by reverting the service deployment. Existing cycle and
event records remain auditable. Static mandate rotation remains the deterministic
fallback and no approved question becomes an executable task automatically.
