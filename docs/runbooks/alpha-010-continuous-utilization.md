# ALPHA-010 Capacity-Aware Continuous Research Utilization

## Purpose

ALPHA-010 keeps the no-capital laboratory productive without confusing machine
utilization with scientific progress. It maintains a bounded queue-depth target and
allocates measured CPU and RAM across eligible work. It never creates a hypothesis,
parameter variant, approval or promotion merely to consume compute.

The priority order is:

1. founder- or mandate-authorized native Bulletproof backtests;
2. preregistered native signal screens on exploration/training partitions;
3. representation and data-quality replays;
4. governed external-evidence acquisition;
5. held-out workflow-skill replay and evaluation.

If none is eligible, the controller reports `eligible_queue_empty` as a stall. It does
not reopen sealed out-of-sample data, broaden data or code authority, or launch capital
work.

## Capacity policy

Eight workers is a ceiling per experiment, not a minimum. The allocator reserves CPU
and free-memory headroom and uses the lower of CPU, RAM and configured worker budgets.
It distributes slots fairly across two normal concurrent backtests and allows a third
only when measured capacity supports the configured minimum per job. Worker count does
not change the frozen variant grid or scientific contract.

VM1 has 36 CPUs and approximately 66 GiB available at the latest observation. With the
production estimate of 4.5 GiB per worker and 8 GiB free-memory floor, the safe initial
budget is 12 workers. Two eligible jobs therefore receive six workers each. Two or
three eight-worker jobs require more measured free memory or a lower peak-RSS estimate
established by representative runs; they must not be promised from CPU count alone.

## Scientific boundaries

Signal screens are outcome-separated discovery instruments, not backtests or promotion
receipts. They use exploration/training partitions, preregistered search families,
multiple-testing budgets and stability/support/cost diagnostics. A surviving effect
freezes a signal contract before strategy engineering. Final OOS remains sealed until
the registered evaluation stage.

Fallback work can produce observations, quality reports or staged skill candidates.
Only the existing ALPHA/BT-009 path may publish a strategy outcome. New code, expanded
data authority, shadow admission, orders and capital retain their existing approvals.

## Visibility and alerting

The native publisher reads the capacity database in SQLite read-only mode and binds its
report to exact control-plane and Bulletproof commits. Hermes retains immutable
snapshots with pending, locked, done and failed counts by work kind, exact running
allocations, configured and active workers, measured RAM, last productive completion
and an explicit scheduler state. Mission Control renders this separately from governed
task stages and scientific receipts.

Three consecutive two-minute observations in `eligible_queue_empty`, `work_queued` or
`resource_blocked` create a founder notification and Telegram alert. A pending job is
not called idle, a running fallback is not called a backtest, and a green daemon is not
sufficient evidence of a productive loop. Utilization telemetry has no scientific,
promotion, execution, order or capital authority.

## Rollout boundary

The deterministic admission/allocation, authoritative queue projections, Mission
Control visibility and low-water alerts are deployed. Production observed the safe
fallback transition and a fresh `fallback_research_running` snapshot with all 12
resource-derived worker slots allocated. This closes the fallback-utilization boundary;
it does not manufacture a standing supply of approved backtests. Existing Bulletproof
output directories remain untracked.

The first fallback implementation is Bulletproof DISC-010 (PR 353). Its replenisher
keeps up to three lower-priority screen assignments present while the native scheduler
uses measured capacity. On the observed VM1 budget, two six-worker jobs may run and a
third remains queued. Eight workers remains a ceiling, not a promise. An approved
backtest has priority over any pending screen; running immutable work is not rewritten
or silently killed to manufacture utilization.

Completed screen receipts are published idempotently into Hermes and become immutable
input to the next ALPHA-004 cycle. Mission Control reports the canonical screen ledger;
local output files remain untracked and are never pushed to Git. A survivor replenishes
the hypothesis-question supply but does not approve code, open final OOS or promote a
candidate.

The installer refuses to restart the resident capacity scheduler while any local or
external worker allocation is active. At a zero-active-work boundary it restarts the
director so its imported dispatch table matches the pinned checkout, then runs the
replenisher every minute. This prevents source/resident-code drift without interrupting
immutable work.
