# M9 Autonomous Mission Supervisor

## Purpose

M9 lets the founder approve one immutable mission plan and delegate its bounded
execution without approving each checkpoint. It does not grant permission to
change the plan, invent commands, widen paths, increase risk, or exceed the
approved time and retry budgets.

## State model

```text
pending_approval -> active -> recovering -> active -> succeeded
                         \-> attention_required
```

- `pending_approval`: the manifest digest is visible, but no task may lease.
- `active`: dependencies and normal worker policy control phase scheduling.
- `recovering`: one explicitly retryable failure was resumed within budget.
- `attention_required`: authority is exhausted or a failure is not retryable.
- `succeeded`: every task checkpoint is terminal and successful.

Legacy missions without a `supervision` block retain task-level approvals.

## Approval boundary

Approval binds the canonical mission manifest SHA-256. A supervised manifest
must carry a rehearsal evidence digest, the rehearsed source commit, a maximum
automatic recovery count, a fixed backoff, and an allowlist of retryable error
categories. Supervised phase tasks do not create separate approval requests.

The founder can approve the plan in Mission Control or through the digest-bound
Telegram review handoff. Telegram notifies only plan approval and
`attention_required` exceptions for supervised missions.

## Recovery boundary

The supervisor:

- reaps expired leases through the existing lease state machine;
- resumes only failures marked retryable or matching the plan allowlist;
- requires unused task attempts, mission time, and recovery budget;
- preserves the task contract, plan digest, artifacts, and event history;
- never completes or fails a task and never holds a task lease;
- escalates nonretryable, over-budget, or expired missions.

The API records every approval, recovery, completion, and exception as a
mission event. Workers remain responsible for process termination and stale
lease rejection.

## Operations

The dedicated VM2 service uses `SWARM_MISSION_SUPERVISOR_TOKEN`, which is
accepted only by `/v1/supervisor/reconcile`. It must not receive an agent,
founder-channel, broker, package-signing, mission-signing, or orchestrator
credential.

```bash
invariance-swarm-mission-supervisor check
invariance-swarm-mission-supervisor once
invariance-swarm-mission-supervisor run
```

Install the unit only after the API migration and secret mount are live:

```bash
sudo worker/systemd/install-supervisor.sh
sudo systemctl enable --now invariance-swarm-mission-supervisor.service
```

## Stop conditions

Pause and investigate when the supervisor reports `attention_required`, the
manifest digest changes, the dedicated credential fails, migration state is
not at the expected head, or a recovery would require new scope or authority.
