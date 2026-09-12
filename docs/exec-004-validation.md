# EXEC-004 Validation

## Result

EXEC-004 adds the Hermes governance half of the idempotent OMS and reconciliation
contract. Bulletproof remains the only producer of command, lifecycle, venue snapshot,
position, balance, discrepancy, and recovery-decision evidence. Hermes stores an
immutable active schema and admits only an exact digest-valid native receipt from
`bt.institutional.oms.oms_reconciliation_receipt`.

## Automated evidence

- Migration head: `e5a9c3f16d40`
- OMS schema create, list, and exact replay routes require orchestrator authority.
- Name/version and specification digests are immutable.
- EXEC-004 quantitative receipts require the active matching OMS schema.
- Wrong producers, changed results, changed receipts, and absent schemas fail closed.
- The cross-repository pilot verifies the schema and receipt by independent GET replay.
- The pilot reports submission eligibility but carries no order or capital authority.

```bash
POSTGRES_PASSWORD_FILE=/path/to/test-secret PYTHONPATH=backend \
  backend/.venv/bin/python -m pytest -q \
  backend/tests/test_oms_schema_registry.py \
  backend/tests/test_quantitative_receipts.py

backend/.venv/bin/ruff check \
  backend/app/models/oms_schema.py \
  backend/app/schemas/oms_schema.py \
  backend/app/services/oms_schema.py \
  backend/app/api/routes/oms_schemas.py \
  backend/app/services/quantitative_receipt.py \
  backend/app/schemas/quantitative_receipt.py \
  backend/alembic/versions/e5a9c3f16d40_add_oms_schema_registry.py \
  backend/tests/test_oms_schema_registry.py \
  backend/tests/test_quantitative_receipts.py \
  worker/scripts/exec004_pilot.py
```

## Claim boundary

Source completion does not certify Bybit or Binance adapters and does not permit a
network order. EXEC-008 retains adapter certification; RISK-004/005 retain candidate
and real-time risk authority; DEMO-001 and LIVE-001 retain capital-path qualification.
