# Capacity-governed parallel Bulletproof execution

Status: local source verified; not activated in production.

## Ownership and budget

Reuse Bulletproof's `orchestrator/global_capacity_scheduler.py`, ResearchDB queue,
whole-process-group pause/resume, RSS accounting and classic hypothesis executor.
Hermes leases authorized assignments, maintains task/operation heartbeats and
publishes terminal receipts through the existing ALPHA-003/BT-009 path. The capacity
director is a deterministic scheduling service, not an LLM deciding financial risk.

An experiment contains at most eight preregistered combinations. Eight is a ceiling,
not a reason to invent redundant variants. Research selects informative combinations
before outcomes; scheduling never changes the grid, dataset, window, costs or gates.
Pools use up to eight spawned workers, limited by actual variant count. Two separately
registered consumers allow different campaigns to enter the shared queue concurrently.
Sequential dependencies within a campaign remain binding.

The sample starts with 16 aggregate slots and two jobs, reserves two CPUs, checks
host load and available RAM, and reserves an initial conservative 2 GiB per worker
plus 8 GiB free headroom. Unconsumed startup reservations are accounted for before
launching another job. This RAM estimate is not a calibrated capacity claim: use
observed representative peak RSS to increase it before admitting larger universes.
Missing memory telemetry stops admission. Memory pressure pauses/resumes whole groups.

All native daemon and agent jobs sharing this budget must use the same ResearchDB
and queue. A separate legacy scheduler database is NOT included automatically;
consolidate it or stop its consumers before activation. Unmanaged jobs are visible
only through system load/RAM, not as individually accounted queue reservations.

## Activation Preconditions

Merge/test the native change from `bulletproof_bt-alpha-capacity` and the matching
worker change first. Do not replace the old checkout's pending resampling work.
Deploy the worker package and native checkout using their reviewed commits.
New immutable task assignments must reference a native commit containing the queue
and parallel driver; an older approved commit must fail rather than silently run
newer code. Existing research approvals and mandates are not expanded.

On VM1, register slot 2 through the existing bootstrap (requires founder operator
environment, including the package signing secret). Use the actual merged worker
commit, not a placeholder, when running:

```bash
sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/alpha002_bootstrap.py \
  --package vm1-alpha-research-executor-capacity-2 \
  --state /etc/invariance-swarm/alpha-capacity-executor-2-state.json \
  --environment /etc/invariance-swarm/alpha-capacity-executor-2.env \
  --source-commit "$(git rev-parse HEAD)"
install -o root -g root -m 0600 /etc/invariance-swarm/alpha003-executor.env \
  /etc/invariance-swarm/alpha-capacity-executor-1.env
bash worker/systemd/install-alpha-capacity.sh
ROOT
```

The installer validates distinct slugs, root-owned mode-600 credentials and native
scripts before retiring the old v2 consumer. It preserves existing custom capacity
configuration. Add all three new units to the VM1 fleet probe's monitored service
list, preserving its existing services; this list is deployment-specific.

## Evidence and Visibility

The native state file is
`/home/omenka/.local/state/invariance-swarm/alpha-capacity-state.json`.
It reports queue counts, running/paused/external worker slots, job IDs and RSS.
Idle agent heartbeats include bounded `research_capacity` metadata; running task
heartbeats include capacity telemetry and stale/missing telemetry is explicit.
Hermes' existing task/operation ledger remains authoritative for each assignment.
No new dedicated Mission Control capacity chart is claimed by this change.

Validate two approved independent assignments: see two distinct task leases and
native queue IDs, up to eight workers each, no duplicate launch while a child is
starting, and two terminal BT-009 publications. Inspect slot/CPU/RAM ceilings and
test pause/resume, restart, stale telemetry and lease cancellation before declaring
operational closure. This production replay has not been performed.

Assignment SHA-256 and Linux PID/start identity bind queued work to a living lease
wrapper. Dead owners or changed bytes fail closed; duplicate immutable submissions
require reconciliation. Cancellation kills the native process group on the next
director poll (sample five seconds); abrupt scheduler death is covered by systemd
control-group termination. Orphan locked jobs count conservatively after restart
and need operator reconciliation; they are not silently retried or forgotten.

## Rollback

Stop both templated executor slots, then stop the capacity director. Preserve queue,
assignment, logs and terminal evidence. Reconcile unfinished rows and task leases
before restoring the old single consumer. Never start both old and new consumers
for the same identity, delete evidence, or interpret cancellation as a scientific
result. No shadow, demo, live, order or capital authority is introduced.
