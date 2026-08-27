# DISC-009 validation

DISC-009 is complete when:

- migrations create immutable portfolios, candidates, and digest-chained events;
- source identity, digest, project, freshness, and source epoch fail closed;
- source uncertainty is derived from canonical evidence;
- exact duplicates and repeated canonical sources are rejected per portfolio;
- scoring is deterministic and normalized by attention cost;
- domain, cluster, selection-count, and attention budgets are enforced;
- a minimum domain-diversity floor prevents research monoculture;
- every unselected candidate retains a counterfactual reason;
- a new portfolio version may reconsider the same canonical sources;
- the API surface contains registration and replay only;
- the production pilot yields genuine digest-bound evidence from live canonical sources;
- no task, execution, promotion, order, or capital authority exists.

Validation commands:

```bash
pytest -q backend/tests/test_discovery_portfolio.py
pytest -q backend/tests
ruff check backend worker/scripts/disc009_pilot.py
```
