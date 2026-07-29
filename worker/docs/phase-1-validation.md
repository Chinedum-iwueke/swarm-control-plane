# Phase 1 Restricted VM1 Worker Validation

Validation date: 2026-07-29 UTC

Branch: `feat/restricted-vm1-worker`

Reviewed worker revision: `38d3e8e68f179be4c533b082a1699107afc8a03e`

Target `main` revision: `d5841393c20dbc0fe2da6736dadcd6ee7b61e33c`

## Recommendation

**NO-GO for enabling or starting the systemd daemon.**

The local worker suite and security review pass, but the controlled live pilot
did not run. Two blocking conditions remain:

1. This noninteractive session cannot read
   `/etc/invariance-swarm/vm1-worker.env`; `sudo -n` reports that a password is
   required. No agent or orchestrator credential was printed or copied.
2. The requested success task pins `base_ref: main`. In an isolated detached
   worktree, compilation succeeds but tests fail during collection because
   `main` imports `datetime.UTC`. The configured worker virtual environment is
   Python 3.10.12, where `datetime.UTC` is unavailable. Python 3.11 is installed
   on the host, but the worker virtual environment and command resolution have
   not been migrated to it.

Do not create the pilot tasks until the runtime mismatch is resolved. Otherwise
the intended success pilot will produce a known failure and consume its single
attempt.

## Test Results

Worker validation:

```text
python -m compileall -q src   PASS
pytest -q                    PASS, 87 tests
ruff check src tests         PASS
ruff check src tests scripts PASS
bash -n systemd/*.sh         PASS
```

`systemd-analyze verify systemd/invariance-swarm-worker.service` reported no
error for the worker unit. The host-wide verifier returned nonzero because it
could not open `/run/systemd/system/netplan-ovs-cleanup.service` and warned
about an unrelated `snapd.service` key.

Repository workflow validation against an isolated `main` worktree:

```text
python3 -m compileall -q .    PASS
pytest -q                    BLOCKED
```

The first test collection error was:

```text
ImportError: cannot import name 'UTC' from 'datetime'
```

Backend development requirements were installed into the local worker virtual
environment before the second workflow check. They are declared by
`backend/requirements-dev.txt`; no repository file was changed by that
installation.

The controlled failure workflow was run in a disposable detached `main`
worktree. `pytest -q worker-pilot-intentional-failure` returned code 4 with a
bounded "file or directory not found" error. It performed no destructive
operation.

## Pilot Tasks

No control-plane task was created, leased, started, completed, failed, or
released during this validation.

| Pilot | Task ID | Status | Event sequence |
| --- | --- | --- | --- |
| Success | Not created | Blocked | None |
| Controlled failure | Not created | Blocked | None |

Consequently, the following live assertions remain unverified:

- assignment to `vm1-developer-coder`
- `attempt_count == 1`
- created, leased, started, heartbeat, and terminal event ordering
- bounded result/failure storage in the live control plane
- absence of credentials in live events and terminal payloads
- live workspace metadata and retained log files
- absence of stale completion following a live failure or lease loss

## Security Review

Verified in code and tests:

- Workflow commands originate only from allowlisted YAML files beneath
  `SWARM_WORKFLOW_DIRECTORY`; task input cannot supply commands or file paths.
- Workflow schemas reject unknown fields, strings in place of argument arrays,
  path traversal, shell metacharacters, absolute executables, privilege tools,
  package/service/network tools, and destructive filesystem commands.
- No production use of `shell=True`, `create_subprocess_shell`, or
  `os.system` was found.
- Workflow Git access is now restricted to read-only subcommands. Workflow
  definitions can no longer add, remove, or prune worktrees.
- The workspace manager resolves repositories as direct children, validates
  containment and metadata, creates detached worktrees, and confines cleanup
  to the workspace root.
- Workflow subprocesses receive a minimal environment without
  `SWARM_AGENT_TOKEN`. Ambient `PYTHONPATH` is discarded and rebuilt from the
  isolated repository (plus its `backend` directory when present), preventing
  imports from a primary checkout.
- API and structured logging code redact bearer values, Authorization headers,
  agent token formats, and lease token formats.
- Executor process groups are terminated on timeout, cancellation, or lease
  loss. Service orchestration suppresses completion and failure after a lease
  conflict/loss.
- Success and failure payloads contain structured, bounded summaries and
  relative log paths rather than complete stdout/stderr.
- Source repository content in the disposable checks remained unchanged; the
  temporary worktrees were removed through Git.

The pilot helper at `scripts/pilot_tasks.py` creates only fixed success or
controlled-failure task contracts. It requires `SWARM_ORCHESTRATOR_TOKEN` in
the environment, does not accept command fields, redacts sensitive keys, and
checks terminal output is no larger than 64 KiB.

## Pilot Procedure

After moving the worker environment to a compatible Python runtime and
successfully running the protected `check`, use a shell that receives both
credentials through a protected environment source. Do not place either token
on the command line.

Create the success task with:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
. .venv/bin/activate
python scripts/pilot_tasks.py create success
```

Run exactly one worker cycle using the protected agent environment:

```bash
sudo bash -c '
set -a
source /etc/invariance-swarm/vm1-worker.env
set +a
exec runuser -u omenka -- \
  /home/omenka/Projects/swarm-control-plane/worker/.venv/bin/invariance-swarm-worker once
'
```

Verify the returned task ID:

```bash
python scripts/pilot_tasks.py verify success TASK_ID
```

Only after the success pilot passes, repeat with `create failure`, one `once`
cycle, and `verify failure`. Inspect the matching workspace's `metadata.json`
and `logs/*.log`, and compare the primary checkout status to a fingerprint
captured immediately before the pilot.

## Known Limitations

- Phase 1 executes one task at a time and preserves all workspaces.
- Isolation is based on systemd restrictions, Unix permissions, subprocess
  process groups, and Git worktrees; it is not a VM or container boundary.
- Workflow processes retain host network access.
- The Python interpreter used by repository tests is determined by the worker
  process environment and currently differs from the minimum implied by
  `main` source code.
- The dedicated failure workflow is a pilot diagnostic and should be removed
  from the allowlist after the controlled failure pilot is complete.
- An orchestrator credential is required to create and inspect pilot tasks; it
  must remain separate from the worker's agent credential.

## Systemd Gate

Installation, enabling, and start commands are intentionally withheld from
the pass path because the recommendation is NO-GO. The existing installation
documentation remains in `worker/README.md`. Do not enable or start the unit
until this report is updated with real task IDs, event sequences, workspace
evidence, and a GO recommendation.
