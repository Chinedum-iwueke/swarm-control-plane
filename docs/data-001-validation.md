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

Production acceptance completed on 2026-08-27 UTC:

- merged source commit: `922884e74922ca000688d90074fa9ac7a0c39204`
- VM2 migration head: `e2d7a4c91b60`
- rebuilt API: healthy, with snapshot registration/list/get and point-in-time resolution routes exposed
- immutable snapshot ID: `b771d529-cd3a-43de-b87d-02fa5307147e`
- immutable snapshot digest: `16c689717341872f0b15d0324122ddbc749d2174197d8f3f4ea7faadf75e3871`
- no-capital pilot: all seven temporal identity and fail-closed checks passed
- retained evidence: `docs/evidence/data001-report.json`

The live proof grants no capital or order authority.
