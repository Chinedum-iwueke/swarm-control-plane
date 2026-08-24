# WS-001 No-Capital Walking-Skeleton Validation

## Scope

WS-001 composes the completed Research Intelligence, registry, Bulletproof and
laboratory-publication contracts. It does not add a second experiment engine,
registry, artifact store, shadow runtime or capital authority.

The live valid-negative path is the completed BT-009 publication
`5cbafb3e-f3e7-5f1a-9678-278368d971fe`. Its canonical receipt links the run, result,
two independent reviews, founder decision and episode; its projection and
Bulletproof-memory receipts are complete. The deliberately invalid path is a
forward auxiliary join and must remain `invalid_attempt`, never `valid_negative`.

## Acceptance command

Run from `worker/` after installing this source revision:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

exec .venv/bin/python scripts/ws001_pilot.py \
  --publication-id 5cbafb3e-f3e7-5f1a-9678-278368d971fe \
  --output /var/lib/invariance-swarm/ws001/report.json
'
```

The verifier fails unless the fresh API client observes a complete publication,
contiguous immutable events, six distinct lifecycle objects, two distinct reviews,
and both projection and memory receipts. It separately proves that the causal
failure is invalid rather than negative and that an injected partial-publication
failure can only pass after `publication_completed`.

## Source validation

```text
PYTHONPATH=src pytest -q tests/test_walking_skeleton.py
3 passed
```

No API key, order endpoint, portfolio allocation or production-promotion authority
is used by this milestone.
