# M9 Autonomous Mission Supervisor Validation

Date: 2026-07-31

## Delivered capability

- digest-bound approval for one immutable supervised mission plan;
- mission-level delegation replacing repeated phase approvals only when opted in;
- persistent supervision status, recovery counters, backoff, and exception data;
- bounded recovery of explicitly retryable failures;
- automatic escalation when attempt, recovery, deadline, or policy authority ends;
- dedicated least-privilege supervisor API credential and daemon;
- Mission Control supervisor status and plan approval;
- Telegram plan approval and exception-only supervision notifications;
- legacy mission approval behavior preserved.

## Security assertions

- no arbitrary task command surface was introduced;
- the supervisor never leases, executes, completes, or fails tasks;
- approval fails when the persisted manifest no longer matches its digest;
- recovery cannot increase task attempts or mission budgets;
- nonretryable failures fail closed to `attention_required`;
- worker stale-lease validation remains authoritative;
- the supervisor token is excluded from errors and has no orchestrator authority;
- supervised tasks remain unleaseable until mission approval activates the mission.

## Automated evidence

- Backend: 35 tests passed.
- Worker: 151 tests passed.
- Telegram gateway: 9 tests passed.
- Mission Control: 23 tests passed.
- Ruff passed on every M9-changed Python file; repository-wide backend Ruff still
  reports 14 pre-existing findings in untouched files.
- Compileall passed for all four application source trees.
- Repository-wide isolated validation: 219 tests passed after adding direct,
  in-worktree Python `src` roots to the validation environment.
- Alembic head: `c8e2f7a41d90`; full offline upgrade SQL generated successfully.
- systemd unit verification: pending on VM2 after the executable is installed.

## Operational pilot

The first pilot mission, `1f580c76-07cf-43dc-b6dc-989e37f1d179`, proved the
single Telegram plan approval and bounded recovery transition. Its first
attempt failed because the isolated validator omitted the Mission Control
`src` root. M9 rearmed it once without another approval. The retry was then
aborted before leasing because correcting the validator moved the symbolic
`main` base ref; executing that changed commit under the old digest would have
violated immutable-plan authority. The replacement pilot is pinned to the
tested commit and is recorded below after execution.

## Recommendation

No-go for enabling the continuous supervisor until the pending test and live
pilot evidence above is complete.
