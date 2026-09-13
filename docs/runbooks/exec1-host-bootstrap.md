# EXEC1 execution-host bootstrap

## Boundary

`exec1-execution` is the dedicated, always-on venue-facing host. VM1 remains the
research and development machine, VM2 remains the control-plane deployment machine,
and the founder Mac remains the local Mission Control machine. EXEC1 does not host
PostgreSQL, Redis, the control-plane API, Telegram, or research workloads.

Provisioning the host does not authorize orders or capital. Venue credentials,
DEMO-001, LIVE-001, runtime-safety state, and founder/risk approval remain separate
gates. Secrets must be supplied through root-owned systemd credentials and must never
enter Git, shell history, fleet telemetry, Mission Control, or Hermes evidence.

## Initial hardening

1. Set hostname `exec1.invarianceresearch.xyz` and create the `omenka` operator with
   key-only SSH access.
2. Disable root login, password authentication, keyboard-interactive authentication,
   and X11 forwarding. Confirm a second key-only session before reloading SSH.
3. Enable UFW with inbound SSH only, fail2ban, unattended security upgrades, chrony,
   and a 2 GiB swap file for the 2 GiB host.
4. Join Tailscale as `exec1`; after private reachability is proven, constrain SSH to
   the tailnet in a separate maintenance window.
5. Verify the actual egress country and call every required venue public/demo endpoint.
   Provider domicile and billing address are not acceptable evidence of egress location.
6. Run `worker/systemd/install-exec1-host.sh` from the reviewed checkout.

The QServers web-console password is a bootstrap credential only. Rotate or lock it
after key enrollment. Do not retain it in any repository artifact.

## Fleet enrollment

On VM1, create the exact read-only observer identity. The state file is root-owned and
contains the one-time agent credential:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/ops004_bootstrap.py exec1 \
  --state /etc/invariance-swarm/ops004-exec1-state.json \
  --source-commit "$(git rev-parse HEAD)"
'
```

Transfer only the returned token to EXEC1 over the authenticated SSH channel. Install
it as `/etc/invariance-swarm/fleet-probe.token`, mode `0600`, root-owned. Configure:

```ini
SWARM_FLEET_API_URL=http://100.112.117.59:8787
SWARM_FLEET_AGENT_TOKEN_FILE=/run/credentials/invariance-swarm-fleet-probe.service/fleet-agent-token
SWARM_FLEET_MACHINE=exec1-execution
SWARM_FLEET_INTERVAL_SECONDS=30
SWARM_FLEET_SERVICES=invariance-swarm-fleet-probe.service,tailscaled.service,chrony.service
```

Run `worker/systemd/install-fleet-probe.sh --enable`, then require three fresh
observations. Mission Control's Fleet Health view discovers the new machine from
`/v1/fleet/health`; it does not use a locally hard-coded machine list.

## Catalog and alerting

Register and activate immutable service catalog `1.1.0` before claiming unified SLO
coverage. Add `exec1-execution=<exec1-private-ip>:22` to the independent watchdog
target set. A missing EXEC1 sample becomes a sustained availability incident;
single-sample network noise does not alert.

## Execution activation

Keep every venue runner disabled until the following are all current: EXEC-003..009,
EXEC-011, PORT-004, RISK-003..005, SHADOW-002, a venue-observed DEMO-001 receipt,
runtime freeze/kill recovery, a dedicated trade-only credential with withdrawals
disabled and IP allowlisting, and exact founder/risk approval. Activate demo before
micro-live. Never share a credential between environments or venues.

The first QServers allocation observed on 2026-09-13 is not an eligible venue host.
Independent IP geolocation places its egress in Oregon, United States; Bybit main and
demo returned HTTP 403 and Binance futures main returned HTTP 451. Binance futures
testnet alone returned HTTP 200. Keep execution disabled and request a genuinely
Nigerian allocation or refund. This host may serve the independent outage-watchdog
role while the location issue is resolved.

## Recovery

Loss of EXEC1 freezes venue submission; it must not move execution onto VM1 or VM2.
Rebuild a replacement host from this runbook, restore only verified state and
credentials through their separate custody paths, reconcile venue orders, fills,
positions and balances, and require a new runtime-readiness receipt before resuming.
