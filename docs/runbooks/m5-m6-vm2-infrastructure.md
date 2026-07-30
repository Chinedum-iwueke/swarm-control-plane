# M5/M6 VM2 Infrastructure Runbook

## Scope

M5 observes the deployed VM2 control plane without mutation. M6 adds one
approved operation: restart only the control-plane API service with pre-state,
post-state, and a reviewed recreate rollback if post-verification fails.

The unprivileged worker cannot access the Docker socket and never runs `sudo`.
A root-owned local broker accepts only an API-signed, short-lived ticket over a
Unix socket. The ticket binds the task, attempt, agent, machine, plan digest,
typed contract, risk, expiry, and deterministic one-time nonce.

The broker has no Linux capabilities. Backup dumps are `0640` beneath a
setgid `2750` directory owned by the dedicated
`invariance-swarm-backup-readers` group. Only the broker receives that group as
a supplementary group; the unprivileged worker does not.

The broker registry contains exactly:

- `observe-control-plane`, risk 0, no approval;
- `restart-control-plane-api`, risk 3, consumed approval required.

It does not accept command strings, paths, service names, hosts, ports, image
tags, environment values, or arbitrary parameters.

## Deployment

Deploy reviewed `main` to VM2 and rebuild the API. Add one root-owned secret:

```bash
sudo install -d -o root -g root -m 0700 /etc/invariance-swarm
sudo bash -c '
set -euo pipefail
umask 077
openssl rand -hex 32 > /etc/invariance-swarm/infrastructure-broker.secret
chown root:root /etc/invariance-swarm/infrastructure-broker.secret
chmod 0600 /etc/invariance-swarm/infrastructure-broker.secret
'
```

Mount that file into the API container as
`/run/secrets/infrastructure_broker_secret` and set
`INFRASTRUCTURE_BROKER_SECRET_FILE` accordingly. The broker reads the original
root-owned file. Never deploy this secret to the unprivileged worker.

Install the worker package in its VM2 virtual environment, then install units
without starting them:

```bash
cd /srv/invariance/swarm/repositories/swarm-control-plane/worker
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
sudo ./systemd/install-infrastructure.sh
```

Create `/etc/invariance-swarm/vm2-infrastructure-worker.env` as root, mode
`0600`, with:

```text
SWARM_API_URL=http://100.112.117.59:8787
SWARM_AGENT_TOKEN=<VM2 agent token>
SWARM_AGENT_SLUG=vm2-infrastructure-operator
SWARM_MACHINE=vm2-deployment
SWARM_BROKER_SOCKET=/run/invariance-swarm-infrastructure/broker.sock
SWARM_INFRASTRUCTURE_WORKSPACE_ROOT=/srv/invariance/swarm/agent-workspaces/infrastructure
SWARM_INFRASTRUCTURE_ROLE_MANIFEST=/srv/invariance/swarm/repositories/swarm-control-plane/worker/role-packages/vm2-infrastructure-operator/manifest.yaml
SWARM_INFRASTRUCTURE_RUNBOOK_DIRECTORY=/srv/invariance/swarm/repositories/swarm-control-plane/worker/infrastructure-runbooks
SWARM_SOURCE_COMMIT=<reviewed 40-character Git commit>
```

Register agent `vm2-infrastructure-operator` with machine `vm2-deployment`,
risk ceiling 3, and capabilities:

- `infrastructure-observation`;
- `service-health`;
- `controlled-restart`.

Register and bind role package `vm2-infrastructure-operator` `1.0.0`. Start only
the broker for checks:

```bash
sudo systemctl start invariance-swarm-infrastructure-broker.service
sudo -u swarm-infrastructure \
  /srv/invariance/swarm/repositories/swarm-control-plane/worker/.venv/bin/invariance-swarm-infrastructure-worker check
```

Keep the continuous worker disabled for supervised pilots.

## M5 Pilot

Using the protected operator environment:

```bash
.venv/bin/python scripts/infrastructure_tasks.py create-observation
```

Run one unprivileged cycle:

```bash
sudo -u swarm-infrastructure \
  /srv/invariance/swarm/repositories/swarm-control-plane/worker/.venv/bin/invariance-swarm-infrastructure-worker once
```

Accept only when the task succeeds at attempt one, the evidence digest matches,
Docker/PostgreSQL/Redis/API health is recorded, storage evidence is bounded,
the latest backup is no older than seven days and passes the PostgreSQL
container's version-matched `pg_restore --list`,
no mutation command ran, and no credential appears.

## M6 Pilot

Create the restart task:

```bash
.venv/bin/python scripts/infrastructure_tasks.py create-restart
```

Inspect its plan digest and pending approval. Approve the exact approval ID with
a bounded expiry:

```bash
.venv/bin/python scripts/governance.py approve \
  --approval-id UUID \
  --reason 'Supervised M6 API-only restart pilot' \
  --expires-in-seconds 900
```

Run one cycle. Accept only when approval events are
`approval_requested`, `approval_granted`, `approval_consumed`; the task events
include lease, start, broker-ticket issuance, and completion in order; pre/post
health pass; only `api` was restarted; no rollback was needed; and evidence
matches the registry.

## Rollback And Removal

The broker automatically attempts only:

```text
docker compose up -d --no-deps --force-recreate api
```

when restart or post-health verification fails. It never repairs PostgreSQL,
Redis, networking, storage, certificates, or source.

Remove units without deleting credentials, evidence, or replay state:

```bash
sudo ./systemd/uninstall-infrastructure.sh --stop --disable
```

Production restore, firewall changes, database migrations, certificate
deployment, Compose edits, package installation, and destructive operations
remain unsupported.
