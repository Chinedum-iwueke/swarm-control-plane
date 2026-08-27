# ML-003 Model-Family and Regime Evaluation

ML-003 compares model families on one verified ML-002 materialization under a current
DISC-007 selection audit. It requires unconditional and linear baselines plus
supervised, unsupervised, regime and meta-label candidates. Every candidate retains the
same ordered causal folds, exact regime slices, class counts, primary metric, log loss,
Brier score and label-permutation control.

Qualification requires incremental value over the strongest baseline, minimum
performance in every declared regime, bounded regime dispersion, sufficient class
support and a passing permutation control. Ranking alone grants no authority.

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/ml003_pilot.py \
  --output /var/lib/invariance-swarm/ml003/report.json
'
```

Rollback stops new evaluations and marks the affected model version ineligible in its
own lifecycle. Existing scorecards remain immutable. ML-003 cannot train, activate,
promote, trade or allocate capital.
