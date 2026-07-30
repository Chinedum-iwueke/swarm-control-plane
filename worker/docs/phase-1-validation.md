# Phase 1 Restricted VM1 Worker Validation

Validation completed: 2026-07-30 UTC

Branch: `feat/restricted-vm1-worker`

Validated worker revision: `53cce0758dcabae68cc45b533796f9dc13890250`

Target `main` revision: `d5841393c20dbc0fe2da6736dadcd6ee7b61e33c`

## Recommendation

**GO for manual systemd installation and start.**

The non-leasing protected `check`, successful one-shot workflow, and dedicated
controlled-failure workflow all passed their acceptance checks. No service was
installed, enabled, or started during validation.

The worker virtual environment was rebuilt with Python 3.11.15. Workflow
subprocesses are pinned to that virtual environment. Repository tests receive
only fixed synthetic test configuration stored inside the isolated workspace;
they do not receive host database, orchestrator, agent, or lease credentials.

## Test Results

```text
python -m compileall -q src scripts  PASS
pytest -q                         PASS, 87 tests
ruff check src tests scripts      PASS
bash -n systemd/*.sh              PASS
worker check                      PASS
systemd-analyze verify            PASS
```

`systemd-analyze` emitted host-level messages about
`netplan-ovs-cleanup.service` permissions and an unrelated `snapd.service`
key. It reported no worker-unit error and returned success.

## Pilot Tasks

| Purpose | Task ID | Status | Attempts |
| --- | --- | --- | --- |
| Initial readiness discovery | `af8fd83e-e12e-4e6e-a910-678823503f89` | Failed as structured | 1 |
| Successful code validation | `23a9489f-94e8-4dad-b00e-ece9b95f259a` | Succeeded | 1 |
| Intentional safe failure | `2940bc80-09b5-4a24-8860-fd7e2dce290b` | Failed as expected | 1 |

All tasks were assigned to `vm1-developer-coder`.

### Initial Discovery

```text
task_created
task_leased
task_started
task_heartbeat
task_heartbeat
task_failed
```

The task exposed a missing test-only PostgreSQL password file without exposing
a password. The terminal failure was bounded and structured:

```json
{
  "error_category": "step_failed",
  "failed_step": "run-tests",
  "retryable": false,
  "return_code": 2,
  "stderr_log": "logs/run-tests.stderr.log",
  "stdout_log": "logs/run-tests.stdout.log"
}
```

There was no completion event after failure. The retained workspace provided
the evidence needed to fix the environment safely.

### Successful Pilot

```text
task_created
task_leased
task_started
task_heartbeat
task_heartbeat
task_completed
```

Both local workflow steps passed:

| Step | Return code | Result |
| --- | --- | --- |
| `compile-python` | 0 | Success |
| `run-tests` | 0 | Success (`1 passed`) |

The API result recorded workflow `code-validation`, repository
`swarm-control-plane`, attempt 1, and base commit
`d5841393c20dbc0fe2da6736dadcd6ee7b61e33c`. It contained step timing,
return codes, and relative log paths but no complete logs. The serialized
result was below the 64 KiB pilot limit.

### Controlled Failure

```text
task_created
task_leased
task_started
task_heartbeat
task_failed
```

The server-local diagnostic workflow ran only:

```text
pytest -q worker-pilot-intentional-failure
```

It safely returned code 4 because the named path does not exist. The API
failure identified `expected-failure`, retained relative stdout/stderr paths,
set `retryable` to false, and contained no stale completion event. The
diagnostic YAML is retained under `tests/fixtures` but was removed from the
runtime workflow allowlist after the pilot.

## Local Evidence

Each attempt created a detached Git worktree beneath
`/home/omenka/Projects/swarm-agent-workspaces`. Metadata recorded:

- task ID and task number
- attempt 1
- repository `swarm-control-plane`
- `base_ref` of `main`
- resolved commit `d5841393c20dbc0fe2da6736dadcd6ee7b61e33c`
- source and isolated repository paths
- creation timestamp

Attempt directories and log directories are mode `0700`. Logs and synthetic
test files are mode `0600`. Success and failure workspaces remain available for
audit.

The primary checkout remained on the worker feature branch and clean before
and after both terminal paths. Its tracked/untracked status fingerprint was:

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

No agent-token, lease-token, Authorization-header, or bearer-token pattern was
found in pilot metadata, logs, API events, result, or failure payloads.

## Security Controls

- Task input contains only structured repository, workflow, and base-ref data.
- Only server-local named workflows are executable.
- Commands are validated argument arrays; no production `shell=True`,
  `create_subprocess_shell`, or `os.system` exists.
- Shells, privilege escalation, package installation, service/network tools,
  destructive filesystem commands, and unsafe Git operations are rejected.
- Workflow Git commands are read-only. Worktree lifecycle commands belong only
  to the workspace manager.
- Repository and workspace paths use containment, symlink, collision, and
  metadata ownership checks.
- Workflow processes run in detached isolated worktrees, never the primary
  checkout.
- Ambient `PYTHONPATH` is discarded and rebuilt from the isolated repository.
- The worker virtualenv is first on child `PATH`.
- Agent and lease tokens are excluded from child environments and redacted
  from structured logs and exceptions.
- Synthetic test files contain fixed noncredential values and remain inside
  the attempt artifacts directory.
- Complete stdout/stderr stays on disk; API payloads contain bounded summaries.
- Process groups terminate on timeout, cancellation, shutdown, and lease loss.
- Lease conflicts suppress stale complete/fail calls.
- Phase 1 processes one task at a time without overlapping executions.

## Known Limitations

- Phase 1 supports only `code_validation` and `code-validation`.
- Workspaces are preserved and require an operator-managed retention policy.
- Isolation uses systemd, Unix permissions, subprocess process groups, and Git
  worktrees; it is not a container or VM boundary.
- Workflow subprocesses retain host network access.
- The repository test emitted upstream FastAPI/Starlette deprecation warnings.
- Backend development dependencies must remain installed in the worker
  virtualenv for the current `main` validation workflow.
- Agent and orchestrator credentials remain separate root-owned files.

## Manual Systemd Commands

Review the pending unit diff and install it without enabling or starting:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo ./systemd/install.sh
```

Explicitly reload systemd:

```bash
sudo systemctl daemon-reload
```

Start the worker without enabling boot-time startup:

```bash
sudo systemctl start invariance-swarm-worker.service
```

Inspect status:

```bash
sudo systemctl status invariance-swarm-worker.service --no-pager
```

Inspect recent logs without following:

```bash
sudo journalctl -u invariance-swarm-worker.service \
  --since "10 minutes ago" --no-pager
```

Follow logs:

```bash
sudo journalctl -u invariance-swarm-worker.service -f
```

Enabling boot-time startup is a separate explicit decision:

```bash
sudo systemctl enable invariance-swarm-worker.service
```

Do not use `enable --now` during the first supervised daemon start.
