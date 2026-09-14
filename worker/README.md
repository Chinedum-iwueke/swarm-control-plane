# Invariance Swarm Restricted Worker

The VM1 worker leases one control-plane task at a time, validates it against a
server-local named workflow, creates an isolated detached Git worktree, runs
the allowlisted validation steps, and reports a bounded result. Phase 1
supports the `code_validation`, bounded `engineering_mission`, and
deterministic `research_experiment` task types
through reviewed local workflows.

## Architecture

The worker has five security boundaries:

1. `SwarmAPIClient` authenticates with a bearer credential and implements the
   task lease lifecycle.
2. The policy layer accepts a structured task contract containing only
   `repository`, `workflow`, and `base_ref`.
3. `WorkflowLoader` loads only allowlisted YAML from
   `SWARM_WORKFLOW_DIRECTORY` and rejects unsafe commands.
4. `WorkspaceManager` creates a detached worktree for each task attempt under
   `SWARM_WORKSPACE_ROOT`. It never runs workflow steps in a primary checkout.
5. The executor runs argument arrays without a shell, uses a minimal child
   environment, streams logs to the workspace, and terminates the process
   group on timeout, lease loss, or shutdown.

The continuous daemon serializes calls to `WorkerService.run_once()`. It never
overlaps tasks and applies bounded backoff only to temporary control-plane
failures.

## Environment

The systemd unit reads `/etc/invariance-swarm/vm1-worker.env`. Keep it owned by
root and mode `0600`. The unit sets `NODE_OPTIONS=--jitless` for Codex-backed
engineering missions so Node can run while `MemoryDenyWriteExecute=true`
remains enforced. It must define:

```text
SWARM_API_URL=http://100.112.117.59:8787
SWARM_AGENT_TOKEN=<provisioned-agent-token>
SWARM_AGENT_SLUG=vm1-developer-coder
SWARM_MACHINE=vm1-developer
SWARM_WORKSPACE_ROOT=/home/omenka/Projects/swarm-agent-workspaces
SWARM_REPOSITORY_ROOT=/home/omenka/Projects
SWARM_WORKFLOW_DIRECTORY=/home/omenka/Projects/swarm-control-plane/worker/workflows
SWARM_ROLE_PACKAGE_MANIFEST=/home/omenka/Projects/swarm-control-plane/worker/role-packages/vm1-engineering-worker/manifest.yaml
SWARM_CODEX_HOME=/etc/invariance-swarm/codex-worker
SWARM_CODEX_MODEL=gpt-5.6-sol
```

Optional settings include:

```text
SWARM_POLL_INTERVAL_SECONDS=10
SWARM_AGENT_HEARTBEAT_SECONDS=30
SWARM_TASK_HEARTBEAT_SECONDS=30
SWARM_LEASE_SECONDS=300
REQUEST_TIMEOUT_SECONDS=30
SWARM_ENGINEERING_TIMEOUT_SECONDS=1800
```

Do not put tokens in command-line arguments, shell history, logs, workflow
files, or task input. The worker redacts known agent/lease token formats and
Authorization headers from its structured logs.

## Security Boundaries

The worker runs as `omenka`, with no Linux capabilities and
`NoNewPrivileges=true`. The systemd unit makes the host and home directory
read-only, except for:

- `/home/omenka/Projects/swarm-agent-workspaces`
- `.git/worktrees` in each approved source repository

Git requires the latter directories to register and prune worktrees. Primary
checkout files remain read-only to the service. The unit also isolates `/tmp`,
blocks kernel/control-group mutation, restricts address families, applies
`UMask=0077`, and sends stdout/stderr to journald.

The agent credential authorizes control-plane access. The separate task lease
token authorizes one task attempt. Neither token is passed to workflow child
processes.

## Setup

Create the worker environment and install the package:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Provision `/etc/invariance-swarm/vm1-worker.env` through a secure root-owned
process:

```bash
sudo install -d -o root -g root -m 0700 /etc/invariance-swarm
sudo install -o root -g root -m 0600 /secure/source/vm1-worker.env \
  /etc/invariance-swarm/vm1-worker.env
```

The source repositories named by `worker/workflows/code-validation.yaml` must
exist as direct children of `SWARM_REPOSITORY_ROOT`.

Engineering missions additionally require the dedicated Codex identity and
setup described in `docs/runbooks/m4-engineering-missions.md`. They produce a
local patch and PR bundle; they do not push, merge, or deploy.

## Commands

Validate configuration, identity, workflows, repository roots, and workspace
permissions without leasing a task:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/vm1-worker.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/invariance-swarm-worker check
'
```

Run exactly one lease cycle:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/vm1-worker.env
set +a
exec runuser -u omenka -- \
  /home/omenka/Projects/swarm-control-plane/worker/.venv/bin/invariance-swarm-worker once
'
```

Run the continuous daemon in the foreground:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/vm1-worker.env
set +a
exec runuser -u omenka -- \
  /home/omenka/Projects/swarm-control-plane/worker/.venv/bin/invariance-swarm-worker run
'
```

Use `--log-level DEBUG|INFO|WARNING|ERROR|CRITICAL` before or after the command.
Do not run `once` or `run` until `check` succeeds.

## Systemd Installation

Review and validate the unit first:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
systemd-analyze verify systemd/invariance-swarm-worker.service
bash -n systemd/install.sh systemd/uninstall.sh
```

Install without enabling or starting:

```bash
sudo systemd/install.sh
```

Enabling and starting require explicit flags:

```bash
sudo systemd/install.sh --enable
sudo systemctl start invariance-swarm-worker.service
```

Alternatively, both actions may be requested together:

```bash
sudo systemd/install.sh --enable --start
```

Inspect status and structured journal logs:

```bash
systemctl status invariance-swarm-worker.service
journalctl -u invariance-swarm-worker.service -f
journalctl -u invariance-swarm-worker.service --since today
```

## Safe Token Rotation

1. Provision a replacement agent credential in the control plane.
2. Stop the worker so it cannot lease with the old token.
3. Write the complete replacement environment to a root-owned temporary file
   without printing the token.
4. Atomically replace `vm1-worker.env`, preserving owner `root:root` and mode
   `0600`.
5. Run `check`, then start the service.
6. Confirm identity and heartbeat health before revoking the old credential.

Never edit the token into a command line or paste it into journald output.

## Operational Control

After the M1 control-plane migration and API are deployed, the protected
operator helper can inspect, pause, resume, and fetch metrics:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane/worker
exec .venv/bin/python scripts/operator_control.py status
'
```

Global pause uses:

```bash
.venv/bin/python scripts/operator_control.py pause \
  --scope global --key all \
  --reason "Operator maintenance" \
  --actor founder-operator
```

Machine and agent keys are supported. A pause prevents new leases at the
control-plane transaction. Stop the systemd unit to cancel and release active
work gracefully.

Workspace cleanup is dry-run by default and removes only API-confirmed terminal
attempts:

```bash
.venv/bin/python scripts/retain_workspaces.py --older-than-days 30
```

See `docs/runbooks/m1-control-and-recovery.md` for deployment, metrics, alert,
retention, backup, and disposable restore procedures.

## VM2 Infrastructure Operator

M5 and M6 add a separate VM2 role. The `swarm-infrastructure` worker remains
unprivileged and communicates with a root-owned broker over a group-restricted
Unix socket. The broker accepts only API-signed, one-time tickets for two
reviewed operations:

- `observe-control-plane`: read-only Docker, PostgreSQL, Redis, API, storage,
  backup, and certificate-state evidence;
- `restart-control-plane-api`: approval-gated restart of only the Compose `api`
  service, with pre/post verification and one fixed recreate fallback.

Task input cannot supply commands, paths, service names, or parameters. The
worker has no Docker socket access; the broker receives no agent credential.
Complete evidence is stored in the infrastructure workspace, registered by
SHA-256 digest, and represented in the task result by a bounded summary.

The dedicated commands are:

```bash
invariance-swarm-infrastructure-worker check
invariance-swarm-infrastructure-worker once
invariance-swarm-infrastructure-worker run
invariance-swarm-infrastructure-broker
```

Installation and supervised pilot steps are in
`docs/runbooks/m5-m6-vm2-infrastructure.md`. The continuous VM2 worker must
remain disabled until both one-shot pilots have passed.

## VM1 Research Runner

The reproducible research runner has a dedicated identity, credential file,
and continuous service. Install and activate it on VM1 with:

```bash
sudo ./systemd/install-research-worker.sh --enable --start
systemctl is-active invariance-swarm-research-worker.service
sudo journalctl -u invariance-swarm-research-worker.service -f --no-pager
```

The unit reads `/etc/invariance-swarm/vm1-research-worker.env`, processes one
research task at a time, and may write only isolated workspaces and Git
worktree metadata. It is independent of the research-memory steward.

## Rollback

Stop the service, restore the previous reviewed worker revision, reinstall the
editable package, validate the unit and `check`, then start it again:

```bash
sudo systemctl stop invariance-swarm-worker.service
cd /home/omenka/Projects/swarm-control-plane
git switch feat/restricted-vm1-worker
# Restore the intended reviewed revision through the normal deployment process.
cd worker
. .venv/bin/activate
python -m pip install -e '.[dev]'
systemd-analyze verify systemd/invariance-swarm-worker.service
```

To remove only the unit:

```bash
sudo systemd/uninstall.sh --stop --disable
```

Uninstallation never deletes the environment file, credentials, workspaces,
logs, or repositories.

## Limitations

- Phase 1 processes one task at a time on one machine.
- Only `code_validation`, low-risk `engineering_mission`, and the dedicated
  synthetic `research_experiment` contract are supported.
- The research pilot cannot read live market data, search parameters, invoke
  Codex, push Git, or promote a finding to production.
- Workflow definitions are static and server-local; task-supplied commands are
  rejected.
- Workspaces are intentionally preserved after success and failure for audit.
- The worker does not push, merge, fetch remotes, or modify primary checkout
  files.
- Isolation uses Unix permissions, systemd sandboxing, and Git worktrees; it is
  not a container or virtual machine boundary.
- The service needs network access for the control-plane API and the dedicated
  Codex model session. Codex-generated child commands use a network-disabled
  workspace-write sandbox.
