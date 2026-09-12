# RISK-003 validation

Hermes stores the immutable RISK-003 policy-schema identity and admits only an exact
receipt from `bt.institutional.risk_budget.dynamic_risk_budget_receipt`. Bulletproof
remains the sole quantitative producer. The registry grants no allocation, capital,
order or promotion authority.

Validation:

```bash
backend/.venv/bin/pytest -q backend/tests/test_risk_budget_schema_registry.py backend/tests/test_quantitative_receipts.py
backend/.venv/bin/ruff check backend/app backend/tests/test_risk_budget_schema_registry.py worker/scripts/risk003_pilot.py
```
