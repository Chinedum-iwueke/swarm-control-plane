# AGT-003 Validation

- Backend: 393 tests passed.
- Worker core service: 18 tests passed on Python 3.12.
- Migration: clean PostgreSQL 16 upgraded through `b3e7a1c52d90 (head)`.
- Contract tests cover valid DAGs, cycles, unknown dependencies, duplicate nodes, attempt-budget overflow, canonical digesting and cooperative cancellation.
- Live pilot evidence is recorded after VM2 deployment; it has no execution or capital authority.
