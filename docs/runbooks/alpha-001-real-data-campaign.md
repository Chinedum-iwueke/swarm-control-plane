# ALPHA-001 Real-Data Campaign Runbook

## Purpose and boundary

ALPHA-001 runs bounded, no-capital research campaigns against immutable Binance or
Bybit history. Bulletproof owns data admission, hypothesis/strategy code, backtests,
truth gates and result artifacts. Hermes freezes the selected DISC-009 questions,
budgets, data identities, lifecycle and evidence receipts. Neither component receives
order, capital, self-approval or live-promotion authority from this package.

An active campaign is not evidence of alpha. A `shadow_candidate` is not approval to
trade. Demo and live activation remain behind SHADOW-002, RISK-003..005,
EXEC-003..009, DEMO-001 and a separately approved LIVE-001 authorization bundle.

## 1. Build the Bulletproof admission receipt on VM1

Use the canonical Bulletproof checkout and its Python environment. The command reads
the panel and acquisition manifests without modifying them.

```bash
cd /home/omenka/Projects/bulletproof_bt

mkdir -p "$HOME/.local/state/alpha001"
PYTHONPATH=src .venv/bin/python scripts/build_alpha_data_admission.py \
  --data-root "$PWD/research_data" \
  --panel "$PWD/research_data/canonical/perp/bybit/BTCUSDT/timeframe=1m/research_panel.parquet" \
  --venue bybit \
  --instrument BTCUSDT \
  --timeframe 1m \
  --source-commit "$(git rev-parse HEAD)" \
  --backup-root "$HOME/.local/share/invariance-swarm/alpha-data-backups" \
  --output "$HOME/.local/state/alpha001/bybit-btcusdt-1m-admission.json"
```

Admission fails for a path outside the canonical root, identity mismatch, absent
required columns, unordered or duplicate timestamps, absent acquisition manifests or
non-successful fetch records. The receipt's claim is deliberately narrower than
exchange attestation: it proves the locally retained bytes and their declared lineage.
The backup is content-addressed recovery evidence for the selected panel, not a
second mutable data lake.

## 2. Deploy Hermes on VM2

```bash
sudo bash <<'ROOT'
set -euo pipefail
repo=/srv/invariance/swarm/repositories/swarm-control-plane
runtime=/srv/invariance/swarm/control-plane-runtime

git -C "$repo" pull --ff-only origin main
cd "$runtime"
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
docker compose up -d --no-deps --force-recreate api

for attempt in $(seq 1 60); do
  status="$(docker inspect swarm-api --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}')"
  [[ "$status" == healthy ]] && break
  sleep 2
done
test "$(docker inspect swarm-api --format '{{.State.Health.Status}}')" = healthy

"$repo/worker/systemd/install-alpha-campaign-director.sh" --enable --start
ROOT
```

## 3. Register and activate on VM1

The matching DATA-002 build, DATA-002 catalog partition, DATA-003 entitlement and one
allocated DISC-009 portfolio must already exist. The bootstrap discovers them by
digest; it never accepts pasted IDs that point to different content.

```bash
cd /home/omenka/Projects/swarm-control-plane/worker

sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

.venv/bin/python scripts/alpha001_bootstrap.py \
  --receipt /home/omenka/.local/state/alpha001/bybit-btcusdt-1m-admission.json \
  --state /etc/invariance-swarm/alpha001-state.json \
  --activate
ROOT
```

If bootstrap reports no matching build/catalog/lake record, register the immutable
panel through the existing DATA-001..003 path first. Do not change the receipt digest
or relax gap/duplicate/entitlement checks to make registration pass.

## 4. Observe and stop

Mission Control shows campaign status, phase, next action, real-data bindings,
budgets, attempts, terminal reason and heartbeat under Research Intelligence.

```bash
systemctl is-active invariance-swarm-alpha-campaign-director.service
sudo journalctl -u invariance-swarm-alpha-campaign-director.service -f --no-pager --output=cat
```

Stopping the director prevents reconciliation but preserves campaigns and attempts:

```bash
sudo systemctl disable --now invariance-swarm-alpha-campaign-director.service
```

Cancel a campaign only through its digest-bound API action. Cancellation and every
negative, invalid or failed attempt remain immutable evidence.

## Operational interpretation

The director closes duration, failure, question and trial budgets and keeps campaign
heartbeats visible. Actual scientific work crosses BT-009: evidence-grounded
hypothesis compilation, registered strategy reuse or bounded engineering generation,
classic-engine execution, truth validation, atomic finalization, independent review
and publication. A contract-only `ready_for_engine_execution` artifact is not accepted
as an attempt result.
