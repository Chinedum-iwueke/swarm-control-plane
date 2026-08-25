# OPS-007 Validation

Date: 2026-08-25

## Delivered

- Canonical `operations` ledger and append-only `operation_events` with migration `b7c3e8a91d40`.
- Idempotent task reconciliation with explicit queued, waiting-approval, running, stalled, blocked and terminal states.
- Independently committed workload heartbeats so client disconnection does not erase operation truth.
- Determinate object/record/edge progress for retrieval and knowledge-graph projection rebuilds.
- Orchestrator APIs for operation inventory, summary and event replay.
- Mission Control global active-work indicator and responsive Activity center.
- Exact failure text, heartbeat age, machine, owner, phase, retry capability and honest indeterminate progress.
- Fifteen-second refresh while work is active or the Activity view is open.

## Automated Evidence

- Backend: `315 passed`.
- Mission Control: `70 passed`.
- Focused operation/projection/graph/health suite: `63 passed`.
- Alembic static upgrade reaches single merge head `c9d4f2a71e30`.
- JavaScript syntax validation passed with `node --check`.
- Ruff passed for all OPS-007 implementation files.
- `git diff --check` passed.

## Visual Evidence

The Activity center was rendered with deterministic demonstration data at 1440x1000 and 390x844. Both viewports showed:

- an always-visible active count;
- running and approval-wait operations without overlap;
- determinate progress with numeric units;
- machine, owner, phase and heartbeat context;
- terminal receipts;
- mobile reflow without horizontal clipping.

State never relies on color alone, errors use an alert region, active-count changes use a contextual status, and reduced-motion preferences disable the indeterminate animation.

## Production Evidence

- VM2 runs repository commit `491ae221204a9f383a100c9340916ac84cded2f3`, API image `invariance-swarm-api:0.4.0`, healthy, at Alembic merge head `c9d4f2a71e30`.
- Mac Mission Control was reinstalled and is running under LaunchAgent `com.invariance.hermes-mission-control` on loopback port `8790`.
- The stale pre-install process formerly owning port `8790` was identified and replaced, preventing old UI code from masquerading as the installed service.
- Live graph operation `c7055a10-0c15-48a5-9faf-367f091a0b54` progressed from `prepare` through node and edge projection to `succeeded` with `1,080` append-only events.
- The terminal receipt recorded `784,223 / 784,223` nodes and `1,368,760 / 1,368,760` edges. Mission Control returned the same operation identity, phase `complete`, terminal state and units.
- Graph status is fresh with manifest `f931765a099aeda5ee3fe8c4dc8225d9843201f8916e64f702a0e5b524f2b277`.
- Follow-up hardening reports corpus-digest progress before graph projection and records `built_at` at actual completion.

OPS-007 is production-observed for governed tasks and instrumented long-running workloads. Idle and unhealthy daemons remain represented by OPS-004 Fleet health rather than being counted as active work. A new workload must use a governed task or the operation reporter before activation; arbitrary process command lines and environments are intentionally outside the ledger because they can contain protected data.
