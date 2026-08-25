# PLAT-001 Validation

PLAT-001 introduces an immutable, versioned service catalog and digest-bound runtime reconciliation ledger.

## Acceptance evidence

- The canonical v1 catalog contains 12 operational services across VM1, VM2, and the founder Mac.
- Every entry declares an owner, recovery owner, runtime kind, machine placement, data classification, SLO, and recovery plan.
- Dependency references are closed over the catalog and self-dependencies are rejected.
- Registration is content-addressed; version/digest conflicts fail closed.
- Activation retains the previous snapshot and supports rollback by reactivation.
- Reconciliation proves the clean runtime contract passes.
- Adversarial reconciliation detects orphan services, stale observations, incompatible interface versions, missing services, unhealthy dependencies, wrong placement, and runtime-kind drift.
- Reports bind the catalog and observations to SHA-256 digests.

The retained report is `docs/evidence/plat001-report.json`; its digest is `9a2c7d868c07783086ad3df410e7ca49385ff750bb58587c1554f0e01a7433d4`.

## Commands

```bash
PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests/test_service_catalog.py
PYTHONPATH=backend worker/.venv/bin/python worker/scripts/plat001_pilot.py \
  --output /var/lib/invariance-swarm/plat001/report.json
```

The API migration is `a4c7e1f92b60`. Production activation is intentionally separate from deployment: migrate/rebuild the VM2 API, register the exact catalog artifact, inspect its digest, then activate it and reconcile live observations.
