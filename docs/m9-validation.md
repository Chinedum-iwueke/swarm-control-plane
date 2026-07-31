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
- Worker: 153 tests passed.
- Telegram gateway: 9 tests passed.
- Mission Control: 23 tests passed.
- Ruff passed on every M9-changed Python file; repository-wide backend Ruff still
  reports 14 pre-existing findings in untouched files.
- Compileall passed for all four application source trees.
- Repository-wide isolated validation: 219 tests passed after adding direct,
  in-worktree Python `src` roots to the validation environment.
- Alembic head: `c8e2f7a41d90`; full offline upgrade SQL generated successfully.
- systemd unit verified on VM2; host verification emitted only pre-existing
  snapd/netplan warnings unrelated to the Hermes unit.

## Operational pilot

The first pilot mission, `1f580c76-07cf-43dc-b6dc-989e37f1d179`, proved the
single Telegram plan approval and bounded recovery transition. Its first
attempt failed because the isolated validator omitted the Mission Control
`src` root. M9 rearmed it once without another approval. The retry was then
aborted before leasing because correcting the validator moved the symbolic
`main` base ref; executing that changed commit under the old digest would have
violated immutable-plan authority. The replacement pilot is pinned to the
tested commit.

The replacement mission, `7b34dfd0-5436-41f7-bba7-fa80cd00e62a`, was approved
once through Telegram with manifest digest
`303be02e59ba51cd3f699fc9dd862807acabfbd9c1149f97e06ea07626fbad39`.
Task `461b73ae-d342-42c8-ae65-4733e82bb64f` succeeded on attempt one against
the exact pinned commit `d4d0b7932ad1921ad7a8df8106c549ee4d7cf0ff`.
Its bounded result recorded successful coding, compile, 219-test validation,
independent review, and PR-bundle steps with no heartbeat failures. The event
order was mission created, mission supervision approved, task leased, task
started, task heartbeats, task completed, mission succeeded, and mission
supervision completed. The supervisor remained active and recorded terminal
`succeeded` with recovery count zero.

The final local audit found Codex-created evidence inherited mode `0644` from
the manual shell even though validation logs and metadata were `0600`. Existing
pilot evidence was immediately restricted, and the executor now forces all
log and artifact files to `0600` and their directories to `0700` independently
of process umask. No credential value was found in result or event payloads.

## Recommendation

**Go** for M9 autonomous supervision of immutable, commit-pinned, rehearsed
missions within explicit time, attempt, recovery, capability, and risk budgets.
**No-go** for symbolic branch refs, scope changes, unclassified recovery,
automatic authority expansion, or execution beyond an `attention_required`
exception.
