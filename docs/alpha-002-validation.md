# ALPHA-002 Validation Record

## Source acceptance

ALPHA-002 adds a dedicated risk-zero VM1 role package, fixed native executor, exact
question/hypothesis resolution, immutable data and commit verification, classic
Bulletproof execution, temporal held-out and doubled-cost evaluation, atomic bundle
retention, native memory precommit, resumable BT-009 publication, campaign task
visibility, bounded retries, timeout and cooperative cancellation.

Source tests cover contract/path/authority rejection, exact typed strategy identity,
unsupported zero-trial retention, temporal holdout isolation, doubled cost drag,
task materialization, terminal failure visibility, cancellation propagation, role
package validation and hardened systemd installation. The complete Hermes backend
suite passed 711 tests, the worker suite passed 253, Mission Control passed 72 and the
Telegram gateway passed 42. The complete Bulletproof suite passed 1,350 tests with 27
declared skips and two pre-existing pandas warnings. Scoped Ruff, Python compilation,
JavaScript syntax, shell syntax, systemd verification and whitespace checks passed.

## Scientific and operational claim boundary

The supported-path proof must use the actual DATA-002/003-admitted Bybit panel and an
exact registered Bulletproof hypothesis at the frozen source commit. It is not enough
to compile a contract or execute a synthetic fixture. The unsupported-path proof must
retain a strategy-engineering requirement and execute zero trials.

ALPHA-002 qualifies continuous no-capital scientific execution only. It does not
establish alpha, future profitability, market connectivity, shadow readiness, demo
readiness or authority to expose the founder's capital. A prospective candidate must
still pass true AGT-006 independence and all later SHADOW, execution, risk, demo and
LIVE gates.

## Test commands

```bash
cd /home/omenka/Projects/bulletproof_bt
.venv/bin/python -m pytest -q tests/test_alpha_research_assignment.py

cd /home/omenka/Projects/swarm-control-plane
POSTGRES_PASSWORD_FILE=/path/to/test-secret backend/.venv/bin/python -m pytest -q \
  backend/tests/test_alpha_campaign.py
PYTHONPATH=worker/src worker/.venv/bin/python -m pytest -q \
  worker/tests/test_alpha_research_executor.py \
  worker/tests/test_alpha_research_systemd.py \
  worker/tests/test_role_package.py
PYTHONPATH=telegram-gateway/src telegram-gateway/.venv/bin/python -m pytest -q \
  telegram-gateway/tests
node --check mission-control/src/hermes_mission_control/static/app.js
```
