# RISK-001 validation

RISK-001 adds a digest-bound drawdown, tail, five-scenario, and reverse-stress dossier. It reuses Bulletproof run and cost evidence and PORT-001 candidate identity without duplicating their analytics.

The service requires price-gap, correlation-break, liquidity-freeze, model-failure, and prolonged-drawdown scenarios. It fails closed on stale evidence or breached drawdown, tail, or scenario envelopes. The live pilot is a deterministic control-path fixture, not empirical validation of a portfolio and not capital, allocation, or order authority.

Validation commands:

```bash
backend/.venv/bin/pytest -q backend/tests/test_risk_stress.py
backend/.venv/bin/ruff check backend/app/models/risk_stress.py backend/app/schemas/risk_stress.py backend/app/services/risk_stress.py backend/app/api/routes/risk_stress.py backend/tests/test_risk_stress.py worker/scripts/risk001_pilot.py
```
