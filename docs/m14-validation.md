# M14 Daily Supervised Research Validation

Status: source, deployment, and first controlled pilot complete; multi-week operational
gate observing from 2026-08-01.

## Implemented controls

- One cycle per research program and UTC date.
- Explicit weekday/hour schedule and weekly cycle ceiling.
- Per-cycle trial and compute budgets.
- Deterministic normalized-question digest.
- Exact duplicate suppression against the immutable hypothesis registry.
- Daily learned, rejected, uncertain, and next-question digest.
- Weekly reproduction, survivor, duplicate, retention, timing, and attention metrics.
- Existing mission-supervisor clock drives reconciliation; no second privileged timer.
- Founder Telegram `/research` visibility and state-change notifications.
- Mission Control dashboard payload includes programs and cycles.

## Automated verification

- Backend: 74 passed, with two upstream deprecation warnings.
- Worker: 171 passed.
- Telegram gateway: 9 passed.
- Mission Control: 23 passed, with one upstream deprecation warning.
- Ruff and compileall passed for all changed surfaces.
- Alembic graph: one head, `f6a8c2d41b70`.

## First controlled pilot

- Source commit: `b406d0c9989d10d3c8593a2c444023cd57208827`.
- ORM boundary repair: `52f0d2b`.
- Program: `d1df30d4-9a40-480b-a1e6-ec9891b328b9`.
- Cycle: `df88225c-697f-4093-876d-a2fd6f47ef8f`.
- Cycle date: `2026-08-01`.
- Question digest:
  `a8165bf51ff0a27db312110c606edf40790ff4684402a50a4bf7068065bb2552`.
- Duplicate hypothesis: `dbfb3e4a-f371-41f3-8a6b-607f813b1c54`.
- Outcome: `duplicate_avoided`.
- Tasks created: zero.
- Trials consumed: zero.
- Weekly duplicate-work-avoided count: one.
- Terminal-babysitting events: zero.
- Next bounded question: extreme BTC perpetual funding rates versus short-horizon
  residual returns after costs.

The pilot proves that the daily program consults immutable institutional memory before
allocating a trial. It did not rerun M13 or create a cosmetically different duplicate.

## Operational gate

M14 source and first-pilot completion do not satisfy the governing multi-week exit gate.
The operational gate requires complete daily records over multiple weeks with no gate
bypass and no terminal babysitting. That observation window cannot be compressed or
simulated into historical evidence.

Implementation decision: **GO** for supervised observation. Production eligibility,
unattended broad search, and any trading authority remain **NO-GO**.
