# OPS-004 Fleet Observability and Founder Alerting

## Scope

OPS-004 observes VM1, VM2, and approved independent hosts such as EXEC1 without collecting process arguments, process
environments, credentials, protected payloads, or arbitrary files. Each Linux probe
publishes a strict authenticated sample every 15–30 seconds. The control plane stores
digest-bound samples, evaluates deterministic sustained-signal rules, records incident
transitions, and uses the existing founder notification outbox for Telegram delivery.

The independent watchdog is installed on an always-on host outside VM1 and VM2. It
uses bounded TCP reachability only and retains its deduplication state locally, allowing
one outage and one recovery notification even when the control plane is unavailable.
The founder Mac is not an availability authority because it may sleep.

## Signals and policy

Raw samples have retention class `telemetry_raw_30d`. They include CPU utilization and
load per core, `MemAvailable`, swap usage/deltas, disk and inode capacity, Linux CPU,
memory and I/O PSI, uptime, OOM deltas, and an explicit systemd service allowlist.

An isolated spike does not alert. Three consecutive breaches open a warning or
critical incident. Three consecutive healthy observations recover it. Availability is
stale after 90 seconds. Each warning, critical, and recovery transition receives one
deduplication key. Founder acknowledgement and bounded silence preserve the event
ledger; neither performs remediation.

## Control-plane deployment

Apply migration `b6f2a9c41d80`, rebuild the API, and verify these routes:

```text
POST /v1/agent/fleet/observations
GET  /v1/fleet/health
GET  /v1/fleet/incidents
GET  /v1/fleet/incidents/{id}/events
POST /v1/fleet/incidents/{id}
```

## Probe preparation

Register one agent for each manifest:

```text
worker/role-packages/vm1-fleet-observer/manifest.yaml
worker/role-packages/vm2-fleet-observer/manifest.yaml
worker/role-packages/exec1-fleet-observer/manifest.yaml
```

Use `worker/scripts/ops004_bootstrap.py vm1`, `vm2`, or `exec1` with distinct mode-0600
`--state` paths and the full deployed source commit. The utility signs or reuses the
exact package, creates the bounded agent and deployment, activates an exact-package
charter and capability grants, binds a scoped workload identity, and writes the token
only into the protected state file. It refuses implicit credential rotation.

For a host registered by a pre-workload-identity version of the bootstrap, repair the
existing objects and credential without rotation:

```bash
worker/.venv/bin/python worker/scripts/ops004_bootstrap.py exec1 \
  --state /etc/invariance-swarm/ops004-exec1-state.json \
  --repair-governance
```

The repair validates the recorded agent, package, deployment, machine, and manifest
digest before creating only missing governance objects. It must report the
`fleet:write` scope before the probe is restarted.

Place each returned credential in a distinct root-owned file readable by the
`invariance-fleet-probe` group. Do not reuse worker or orchestrator credentials.
Create `/etc/invariance-swarm/fleet-probe.env` on the target host:

```bash
SWARM_FLEET_API_URL=http://100.112.117.59:8787
SWARM_FLEET_AGENT_TOKEN_FILE=/run/credentials/invariance-swarm-fleet-probe.service/fleet-agent-token
SWARM_FLEET_MACHINE=vm1-developer
SWARM_FLEET_INTERVAL_SECONDS=20
SWARM_FLEET_SERVICES=invariance-swarm-worker.service
SWARM_FLEET_DISK_PATH=/
```

Use `vm2-deployment` and the reviewed VM2 service allowlist on VM2. Then install:

```bash
sudo worker/systemd/install-fleet-probe.sh --enable
systemctl is-active invariance-swarm-fleet-probe.service
journalctl -u invariance-swarm-fleet-probe.service -n 30 --no-pager
```

## Independent watcher

On an always-on third observer, create a distinct Telegram bot credential file and:

```bash
SWARM_WATCHDOG_TARGETS=vm1-developer=VM1_TAILSCALE_IP:22,vm2-deployment=100.112.117.59:8787
SWARM_WATCHDOG_TELEGRAM_TOKEN_FILE=/etc/invariance-swarm/fleet-watchdog-telegram.token
SWARM_WATCHDOG_FOUNDER_CHAT_ID=8787936915
SWARM_WATCHDOG_INTERVAL_SECONDS=30
SWARM_WATCHDOG_FAILURE_SAMPLES=3
SWARM_WATCHDOG_RECOVERY_SAMPLES=3
```

Install with `sudo worker/systemd/install-fleet-watchdog.sh --enable`. This credential
is an alert-only fallback and must not be the founder intake bot token.

## Verification and rollback

Compare live values with `/proc/meminfo`, `/proc/pressure/*`, `/proc/vmstat`,
`statvfs(2)`, and `systemctl is-active`. Rehearse one transient fault, one sustained
fault, recovery, service restart, clock skew, duplicate sample, single-host outage and
simultaneous-host outage. Retain the incident/event IDs and Telegram delivery evidence.

Rollback disables the probe and watchdog services. It does not delete observations,
incidents, events, or acknowledged notifications.
