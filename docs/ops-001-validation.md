# OPS-001 Approval And Readiness Race Closure

Date: 2026-08-14

## Outcome

OPS-001 replaces mutable-state polling as the founder notification contract with
a PostgreSQL-backed outbox. Approval gates are created durably in `waiting`,
become `pending` only when their dependencies and mission are ready, and are
acknowledged only after Telegram accepts delivery. Gates whose digest or state
is no longer current are superseded.

Approval now commits an explicit `task_ready` task event and outbox record in the
same transaction that queues the task. A supervised mission is also scheduled
for immediate reconciliation. Continuous workers remain the execution trigger;
no manual `once` call is part of the lifecycle contract.

## Contract

1. Creating an approval creates one digest- and generation-bound outbox gate.
2. Blocked gates remain durable but are not delivered.
3. At most the currently actionable dependency gate is presented.
4. Telegram acknowledges a notification only after a successful send.
5. Failed delivery remains pending for bounded polling retry.
6. Approval emits `approval_granted`, `task_ready`, then permits `task_leased`.
7. Re-armed approval generations receive distinct gates and readiness records.
8. Expired or changed handoffs cannot authorize a stale digest.
9. Tokens, authorization headers and secret values are absent from payloads.

## Validation

- Backend suite: 241 passed.
- OPS-focused backend tests: 19 passed.
- Telegram gateway suite: 12 passed.
- Ruff: changed backend and Telegram files pass.
- Compileall: backend and Telegram source pass.
- Wider worker suite: 178 passed, 10 pre-existing environment-sensitive
  executor/Postgres fixture failures. OPS-001 does not modify worker execution.

Production migration, API recreation and Telegram service restart are required
before the live transcript can be retained.

## Rollback

Stop the Telegram gateway before rolling the API back. Revert the application
release, downgrade Alembic from `d8b4f1a72c90`, then restart the prior gateway.
Existing task, approval and event records are not altered by the downgrade; only
undelivered notification records are removed.
