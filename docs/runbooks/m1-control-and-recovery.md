# M1 Control, Visibility, Retention, and Recovery Runbook

## Scope

This runbook covers:

- supervised VM1 worker operation;
- global, machine, and agent pause/resume;
- authenticated control-plane metrics and alerts;
- workspace retention;
- control-plane PostgreSQL backup and disposable restore verification.

It does not authorize production restore or destructive database operations.

## Prerequisites

- migration `d3f1a8c9b420` is applied on VM2;
- `/etc/invariance-swarm/vm1-worker.env` is root-owned mode `0600`;
- the operator environment is root-owned mode `0600`;
- VM1 worker virtualenv uses Python 3.11;
- Prometheus receives an orchestrator credential through its secret mechanism;
- PostgreSQL backup uses a dedicated role and mode-`0600` `PGPASSFILE`.

## Supervised Worker

```bash
sudo systemctl start invariance-swarm-worker.service
sudo systemctl status invariance-swarm-worker.service --no-pager
sudo journalctl -u invariance-swarm-worker.service --since "10 minutes ago"
```

Stop:

```bash
sudo systemctl stop invariance-swarm-worker.service
```

## Operator Environment

For examples below:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/operator_control.py status
'
```

The helper never prints the credential.

## Pause and Resume

Global pause:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/operator_control.py pause \
  --scope global --key all \
  --reason "Operator maintenance window" \
  --actor founder-operator
'
```

Machine pause:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/operator_control.py pause \
  --scope machine --key vm1-developer \
  --reason "VM1 maintenance" \
  --actor founder-operator
'
```

Agent pause uses `--scope agent --key vm1-developer-coder`.

Resume uses the same command with `resume` and a reason. Pause prevents new
leases at the control-plane transaction. It does not revoke an active lease;
use systemd stop for a graceful active-task cancellation and release.

## Metrics and Alerts

Inspect authenticated Prometheus output:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/operator_control.py metrics
'
```

Metrics include:

- tasks by state;
- enabled and online agents;
- active leases and oldest active-lease age;
- paused scopes by type.

Prometheus rules are in `ops/prometheus/hermes-alerts.yml`. Route alerts to the
founder notification channel configured on VM2. A global pause is informational;
no online worker is critical; an active lease older than 20 minutes is warning.

## Workspace Retention

Policy:

- retain failed attempts for at least 30 days;
- retain successful attempts for at least 14 days;
- retain incident/legal/benchmark evidence until explicitly released;
- never delete a nonterminal task workspace;
- retain registered artifacts according to their independent policy.

The Phase 1 tool uses one conservative age for all terminal workspaces.

Dry-run candidates older than 30 days:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
export SWARM_WORKSPACE_ROOT=/home/omenka/Projects/swarm-agent-workspaces
export SWARM_REPOSITORY_ROOT=/home/omenka/Projects
cd /home/omenka/Projects/swarm-control-plane/worker
exec runuser -u omenka --preserve-environment -- \
  .venv/bin/python scripts/retain_workspaces.py --older-than-days 30
'
```

Review every candidate. Apply by adding `--apply`. Cleanup validates API
terminal state, metadata ownership, path containment, and Git worktree state.

## PostgreSQL Backup

Create `/etc/invariance-swarm/control-plane-backup.env` root-owned mode `0600`
with nonsecret connection coordinates and paths:

```text
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=swarm_control
PGUSER=swarm_backup
PGPASSFILE=/run/secrets/swarm_backup_pgpass
HERMES_BACKUP_DIR=/srv/invariance/backups/swarm-control-plane
```

The pgpass file contains the password and is never passed as an argument.

Run:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/control-plane-backup.env
set +a
exec /srv/invariance/swarm-control-plane/ops/control-plane-backup.sh
'
```

The script writes a mode-`0600` custom-format dump and SHA-256 manifest only
after `pg_restore --list` verifies readability. Copy backups to encrypted
offsite storage through a separately reviewed workflow.

Recommended minimum retention:

- 7 daily;
- 4 weekly;
- 6 monthly;
- one verified encrypted offsite copy.

## Disposable Restore Drill

Do not restore over production.

1. Select a registered backup and verify its SHA-256 manifest.
2. Create a disposable database with a dedicated restore-test role.
3. Run `pg_restore --no-owner --no-acl` into that disposable database.
4. Apply the repository migration command through the reviewed deployment
   procedure.
5. verify tables, latest migration, agent/task/event counts, append-only
   triggers, and API health.
6. Record duration, backup digest, row-count checks, and errors.
7. Drop the disposable database only after evidence is registered.

Production restore requires a separate approved recovery plan, traffic pause,
target confirmation, rollback decision, and explicit founder authorization.
