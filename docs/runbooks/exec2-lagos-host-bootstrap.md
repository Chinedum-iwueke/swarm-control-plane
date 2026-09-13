# EXEC2 Lagos venue-host bootstrap

## Boundary

`exec2-lagos` is the dedicated venue-facing demo and future micro-live host. VM1 owns
research and Bulletproof computation, VM2 owns the control plane, the founder Mac owns
Mission Control, and EXEC1 remains the independent observer. EXEC2 does not host the
control-plane databases, API, Telegram gateway, or research workloads.

Provisioning does not authorize orders or capital. Venue credentials, environment
selection, candidate admission, runtime risk, founder approval, and DEMO-001/LIVE-001
receipts remain orthogonal gates. The installation must finish with execution disabled.

## Host and network admission

1. Require hostname `exec2-lagos.invarianceresearch.xyz` and key-only `omenka` SSH.
2. Disable root, password, keyboard-interactive, and X11 SSH access only after a fresh
   operator-key session succeeds.
3. Enable UFW, fail2ban, unattended upgrades, chrony, Docker, and a 2 GiB swap file.
4. Join the established Tailscale network as `exec2-lagos`; management and control
   traffic use Tailscale while venue traffic uses the static Nigerian public egress.
5. Verify the server-observed public IP resolves to `NG` and require HTTP 200 from
   Bybit main/demo and Binance spot/futures public time endpoints.
6. Run `worker/systemd/install-exec2-lagos-host.sh` from the reviewed checkout.

Never install venue secrets during host bootstrap. Exchange credentials must be
trade-only, withdrawal-disabled, IP-bound, environment-specific systemd credentials.

## Fleet enrollment

On VM1, create the exact observer and its workload identity:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/ops004_bootstrap.py exec2 \
  --state /etc/invariance-swarm/ops004-exec2-state.json \
  --source-commit "$(git rev-parse HEAD)"
'
```

Transfer only the agent token to `/etc/invariance-swarm/fleet-probe.token` on EXEC2.
Configure the probe with machine `exec2-lagos`, API `http://100.112.117.59:8787`, a
20-second interval, disk `/`, and the allowlisted services `tailscaled`, `chrony`,
`docker`, `fail2ban`, and `unattended-upgrades`. Require at least three accepted samples.

## Execution admission

After fleet enrollment, install no order-capable daemon until EXEC-003 through EXEC-009,
EXEC-011, PORT-004, RISK-003 through RISK-005, and SHADOW-002 evidence is current.
DEMO-001 must then certify authenticated Bybit demo order placement, partial fills,
cancel/amend, disconnects, duplicate suppression, restart reconciliation, stale-data
abstention, and kill recovery on this exact host and IP. LIVE-001 remains a separate
founder-approved micro-live transition with its own credential and limits.

## Recovery

Loss of EXEC2 freezes submission and must not relocate execution to VM1 or VM2. EXEC1
must alert independently. Rebuild from this runbook, restore only verified state and
credentials, reconcile venue state, and issue a new readiness receipt before resuming.
