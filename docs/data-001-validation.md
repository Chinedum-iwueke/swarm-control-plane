# DATA-001 Validation

## Contract evidence

- Stable instrument IDs are independent from effective-dated venue symbols.
- Market-effective and knowledge-availability clocks are distinct and mandatory.
- Snapshots and revisions are immutable and digest bound.
- Symbol reuse, listing revisions and reference revisions cannot overlap ambiguously.
- Unknown venue/symbol/time identity fails closed.
- Sessions use declared IANA timezones and explicit holiday calendars.
- Corporate actions are visible only after their availability time.
- A resolution retains the exact snapshot digest and bounded claim.
- The service grants no order, execution or capital authority.

## Automated evidence

Targeted tests cover symbol change, relisting semantics, present-day leakage, future snapshots, clock skew, overlapping symbol reuse, holiday and 24-hour sessions, explicit delisting, unknown venue, digest mismatch, idempotency, ordered supersession and registered routes. Existing DATA contract tests remain green.

```bash
POSTGRES_PASSWORD_FILE=/path/to/test-secret \
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_reference_data.py backend/tests/test_data_contracts.py -q
backend/.venv/bin/ruff check \
  backend/app/models/reference_data.py \
  backend/app/schemas/reference_data.py \
  backend/app/services/reference_data.py \
  backend/app/api/routes/reference_data.py \
  backend/tests/test_reference_data.py \
  backend/alembic/versions/e2d7a4c91b60_add_point_in_time_reference_data.py \
  worker/scripts/data001_pilot.py
```

## Production acceptance

Production completion requires migration `e2d7a4c91b60` at head, a healthy rebuilt VM2 API exposing all four reference-data routes, and a successful no-capital pilot report. Record the merged source commit, snapshot digest and report digest here after deployment.
