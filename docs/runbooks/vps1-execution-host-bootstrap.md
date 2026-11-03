# VPS1 execution-host bootstrap

## Boundary

`vps1-execution` is the sole venue-facing demo and intended micro-live host. VM1
owns research and Bulletproof computation, VM2 owns the control plane, and the
founder Mac owns Mission Control. VPS1 does not host control-plane databases,
research workloads, or an independent-watchdog role.

Provisioning does not authorize orders or capital. Venue credentials,
environment selection, candidate admission, deterministic risk, founder approval,
and DEMO-001/LIVE-001 receipts remain separate gates. Installation must finish
with execution disabled.

## Host and network admission

1. Require hostname `vps1.invarianceresearch.xyz` and key-only `omenka` SSH.
2. Add the distinct VM1, VM2, and founder-Mac public keys before disabling root,
   password, keyboard-interactive, and X11 SSH access.
3. Join Tailscale as `vps1-execution`; use Tailscale for management/control traffic
   and the static Nigerian address for venue egress.
4. Run `worker/systemd/install-vps1-execution-host.sh` from the reviewed commit.
5. Require Nigerian egress plus HTTP 200 from Bybit main/demo and Binance
   spot/futures public-time endpoints.

The installer creates protected, initially empty credential files at:

```text
/etc/invariance-swarm/execution/credentials/bybit-demo.env
/etc/invariance-swarm/execution/credentials/bybit-live.env
```

Both are root-owned mode `0600`. Never put secrets in Git, shell history, bootstrap
state, fleet telemetry, or Mission Control. Credentials must be trade-only,
withdrawal-disabled, IP-restricted, and environment-specific.

## Fleet enrollment

On VM1, register the exact observer package and workload identity:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/ops004_bootstrap.py vps1 \
  --state /etc/invariance-swarm/ops004-vps1-state.json \
  --source-commit "$(git rev-parse HEAD)"
'
```

Transfer only the returned agent token to
`/etc/invariance-swarm/fleet-probe.token` on VPS1. Configure machine
`vps1-execution`, API `http://100.112.117.59:8787`, a 20-second interval, disk
`/`, and allowlisted services `tailscaled`, `chrony`, `docker`, `fail2ban`, and
`unattended-upgrades`. Require three accepted samples before declaring visibility.

## Execution admission and recovery

Install no order-capable daemon until its exact environment, host, egress IP,
credentials, risk rules, reconciliation path, and kill controls have current
certification. DEMO-001 must be rerun on VPS1 before any live consideration.
LIVE-001 remains a separate founder-approved transition.

Loss of VPS1 freezes submission and must not relocate execution to VM1 or VM2.
Rebuild from this runbook, restore only verified state and credentials, reconcile
venue state, and issue a new readiness receipt before resuming.
