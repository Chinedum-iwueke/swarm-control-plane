# GOV-004 validation

GOV-004 is complete when:

- proposal, task, approval, control, operation, policy, delegation, exception,
  decision, lifecycle and consequence records export through one stable schema;
- a fresh client verifies the Ed25519 signature and reconstructs lifecycle projections;
- tampering, omission, reordering and signature forgery fail closed;
- clock disorder does not corrupt the explicit canonical sequence;
- sensitive values are replaced by path-bound digest receipts;
- exports remain retrievable as immutable records; and
- the production pilot proves valid replay and invalid replay without granting capital
  or order authority.

Verification commands:

```bash
pytest -q backend/tests/test_governance_audit.py \
  backend/tests/test_authority_policy.py \
  backend/tests/test_institutional_lifecycles.py \
  backend/tests/test_lifecycle_consequence.py
ruff check backend/app backend/tests/test_governance_audit.py
python -m compileall -q backend/app worker/scripts/gov004_pilot.py
```
