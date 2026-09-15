# Backtest activity and production truth audit

2026-09-15. Hermes projects task custody and native receipts; Bulletproof remains
the sole quantitative executor, evaluator and capacity scheduler.

Mission Control Research now has a paginated Backtest queue, with waiting,
running and finished filters, tier filters, frozen data/window/code bindings,
heartbeats, execution phases, trial counts, failed gates, retained native metrics
and receipt digests. Planning success does not imply an executed backtest.
Shadow-review requests do not establish admission or live authority. Missing
native metrics are not synthesized from task status. Refresh preserves expanded
evidence details; failed requests visibly mark the queue unavailable.

## Production evidence and remaining closure

Both VM1 capacity consumers and the director are active and authenticated after
activation at 18:52 UTC. Discovery workers restarted at 18:56 UTC with the fixed
jitless subprocess environment. The existing capacity queue has zero jobs.
The next post-fix discovery attempt and two overlapping terminal BT-009 attempts
remain outstanding. Do not count classic fixture parity as this production proof.

The approved weekly mandate has 21 discovery cycles, zero hypotheses and zero
trials. It binds only BTCUSDT, 2026-04-01 through 2026-05-01, and native commit
67e5db0488a8495f7badfb2e89857cd29c72c383. Its immutable approval cannot authorize
the new one-year/current-engine path. The mandate CLI now permits explicit
source campaign, distinct key/version, reviewed commit and timezone-bound
window overrides. Explicit windows require at least 365 days. This creates a new
approval request, never broadens an existing approval. Catalog/PIT availability
checks still determine whether the requested window is executable.

RI-014D has a demonstrated source-bound just-in-time assurance receipt, not
global equation fidelity. The scientific benchmark still has 20 pending
adjudications and no measured accuracy. RI-015 has no live evaluation runs.
RI-016 freshness/parity is demonstrated, but does not prove scientific reasoning.
Literature-grounded senior research is wired; productive post-fix discovery is
not yet demonstrated. No capital or order authority was changed.

## Verification

- Backend activity tests: 10 passed, including authentication, stage boundaries,
  receipt/metric custody, pagination and heartbeat projection.
- Mission Control suite: 78 passed.
- Worker suite: 283 passed before the two admission-binding regressions; the
  final focused mandate suite has six passing tests.
- Desktop 1440px and mobile 390px Playwright checks passed: filters, pagination,
  detail preservation, no horizontal overflow and no JavaScript errors. Ruff,
  JavaScript syntax and whitespace checks passed.

## New mandate request and admission refresh

The panel's Parquet metadata spans 2021-01-01 to 2026-05-18 with 2,827,851 rows.
This supports requesting a one-year window, not a claim of complete usable
coverage for every auxiliary field. Execution availability gates remain binding.

The first new-commit mandate request correctly failed before writing a mandate:
the existing admission receipt bound the older native commit. Rebuilt admission
under explicit `PYTHONPATH=/home/omenka/Projects/bulletproof_bt/src`, after checking
both the import path and checkout commit. This matters because the shared native
virtualenv still has an editable package pointing at an older worktree. The
verified producer reread identity/lineage and SHA-256 of the unchanged panel.
Registered receipt `09c3b6a6-b7d5-4efe-88a6-637259ab47ce`, digest
`eadd66dbc7d6091db9db10e0e138abe20290ad941332ad142259c748e355d201`,
binds the reviewed `a864ac0` engine with no financial authority.

New mandate `aae38741-7f41-40bc-8612-0ba266467a55`, key
`ALPHA004-CAPACITY-20260915`, digest
`311dd79128e35416091545cc16d5c95334917bc9ae0bf1d7eb24151b9a09e974`,
was requested through Mission Control's existing operator client and is awaiting
founder approval. Do not rerun the creation command or reuse old approvals.
The following is the reproducible request, not an outstanding setup command:

```bash
sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/alpha004_mandate.py \
  --mandate-key ALPHA004-CAPACITY-20260915 \
  --source-campaign-id fb19a294-58b8-45fa-9259-4d60f34d8e24 \
  --bulletproof-source-commit a864ac0910890f98f457eb4140b28ede9921e91d \
  --producer-receipt-id 09c3b6a6-b7d5-4efe-88a6-637259ab47ce \
  --window-start 2025-05-01T00:00:00Z \
  --window-end 2026-05-01T00:00:00Z
ROOT
```

The command requests approval; it does not approve or launch research itself.
An existing key/version is immutable: inspect conflicts, do not overwrite it.

## Deployment verification

Control-plane PR #262 merged at `f22fe150f`. VM2 built/running image identities
match `sha256:a933025365098c812a638b5fcd1a67d0b49a379b98853487c6bfe3f32c144a59`;
health passes and migration remains `b1e7f9a03c62`. Mission Control on Mac was
reinstalled and its launch agent is running. Its live desktop and mobile checks
show all 12 historical tasks, including the eight-trial negative Tier2B result,
without scroll jumps, horizontal overflow or JavaScript exceptions.
