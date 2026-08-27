# ML-002 Causal Feature, Label and Split Pipelines

## Purpose

Register a reproducible machine-learning dataset projection without allowing future
information into features, labels, transforms or validation folds.

## Contract

1. Register or select a DATA-002 immutable dataset build.
2. Select an active DISC-003 factor program over the same dataset manifest.
3. Register `/v1/research/causal-pipelines` with explicit feature availability, label
   end offsets, train-only fitted transforms, purge, embargo and expanding folds.
4. Materialize the compiled pipeline outside the API.
5. Independently rebuild it and register the equal content digests plus every fold's
   causal checks at `/v1/research/causal-pipelines/materializations`.

The API rejects manifest-lineage drift, unknown factors, label-horizon drift,
insufficient purge, overlapping embargo, non-expanding folds, validation-fitted
transforms, failed point-in-time checks and rebuild mismatch.

## Pilot

Run on VM1 after the API migration is deployed:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/ml002_pilot.py \
  --output /var/lib/invariance-swarm/ml002/report.json
'
```

## Rollback

Stop accepting new pipeline and materialization registrations and pin downstream work
to the last verified compiled digest. Existing manifests and receipts remain immutable
and readable. ML-002 grants no training, inference, promotion, order or capital authority.
