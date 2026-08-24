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

## Live completion evidence

Completed on 2026-08-24 against the VM2 control plane using publication
`5cbafb3e-f3e7-5f1a-9678-278368d971fe`.

| Evidence | Value |
|---|---|
| Report digest | `7e91e1219a6f764a2cb0c6b07b39fdd2cd27e770117a4f1c7452ea543eb807ce` |
| Valid-negative bundle | `293424d8e8923568bb2150dfaea2cdfaf1153ba3d5b87925aa99fd3999688720` |
| Publication event digest | `330c93ee12704c6e74646cbbec3be45870cd7f91b4ca0adfa89c39c54df8a62c` |
| Invalid fixture digest | `aa5b78010c398b030db4f299c85edbf041c1ef3ada1099665d442e9834bcbff0` |
| Invalid outcome record | `f54be6e2-24ce-4dbf-a4b0-7c64cf19ed0f` |
| Invalid run object | `5cbc2ce4-e2c5-55fa-b558-2e56c665f9bd` |
| Compensation event digest | `583390c4006a22047edcaa88d2b2b91227345bb54991a509d4a50c27f76a558a` |

The publication replay contained six distinct canonical lifecycle objects and four
contiguous events. The injected forward join was retained as `invalid_attempt`, the
memory-publication failure recovered, and the report declared
`capital_or_order_authority=false`.
