# BT-009 Governed Research Bridge

## Preconditions

- The control-plane API includes migration `e8b1c4d72f90`.
- A native Bulletproof qualification root contains `result.json`, the approved
  proposal, dataset snapshot, truth receipt, and 16 finalized bundles.
- `SWARM_API_URL` and `SWARM_ORCHESTRATOR_TOKEN` are loaded from the root-owned
  operator environment.
- The Bulletproof source checkout equals the commit recorded by the qualification.

## Execute

Run from the worker directory as the operator:

```bash
.venv/bin/python scripts/bt009_live_pilot.py \
  --qualification-root /path/to/qualification \
  --bulletproof-root /path/to/bulletproof_bt \
  --state /etc/invariance-swarm/bt009-live-state.json \
  --memory-db /srv/invariance/swarm/research-memory/bt009-publications.sqlite
```

The command registers the immutable proposal, source, dataset, hypothesis,
experiment, and all trials before publishing the selected result. It then records
two independent reviews, retains the negative decision, publishes canonical run
evidence, refreshes stale projections, writes research memory, and verifies the
event replay.

## Verify

The final output must report:

- `bridge_state: complete`
- `publication_state: complete`
- `registered_trials: 16`
- `outcome: rejected`
- a nonzero `event_count`

The state file must remain root-owned and mode `0600`.

## Failure behavior

The bridge is monotone. A stage cannot be skipped, reordered, or overwritten with
a different receipt. Publication never proceeds without current graph and
retrieval epochs, and memory is never written before canonical publication.

No rollback deletes research evidence. A failed attempt is retained and resumed
from its last immutable receipt after the operational fault is corrected.
