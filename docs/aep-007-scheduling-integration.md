# AEP-007: scheduling, authority and visible recovery

Status: in progress, not commissioned. AEP-005/AEP-006 are not yet the production
default. This milestone must not be described as complete based on local episode
tests alone.

## Verified implementation increment

The existing engineering executor now checks its task lease through a heartbeat
before every stage and checks the current billing lane's provider permit before
reserving a model call. Deterministic stages do not require a provider permit.
Drain pause continues to prevent new leases through the existing control plane;
it is not converted into cancellation of an already executing task.

The provider permit endpoint exposes a stable circuit revision. Deferred episodes
require a changed trusted recovery token; repeated delivery with the same token
does not repeat model spend. The executor uses a healthy circuit revision only for
capacity recovery, not to reopen an infrastructure deferral. Deadlines, repairs,
call reservations, receipts and source bindings remain unchanged. Lost leases
prevent new effects. Already launched work remains charged after interruption.

Capacity deferral is returned through the existing worker provider-capacity
protocol, including when no model was launched. Subscription/API lane identity is
preserved. There is no wall-clock or random retry token.

Stage-boundary heartbeats and the final execution summary expose stage, status,
blocker, repairs and call budgets, deadline, recent receipt IDs and usage
completeness. This provides telemetry through existing task progress; it is not
a claim that a dedicated Mission Control episode inspector has been implemented.

## Remaining acceptance work

- Discovery producers must supply the new typed method request with complete
  scientific identity, evidence, obligations and permitted repair fields. The
  initial task adapter supports `design_adequacy_v1`; other diagnostic tools
  still need explicit adapters rather than model-selected commands.
- Publish exact method packets into separately leased AEP-005 reviewer tasks;
  verify registry identity, dependencies and authority on cached results as well
  as fresh results. Never relabel legacy approvals as AEP-005 evidence.
- Materialize AEP-006 engineering tasks from those accepted packets, with
  explicit focused-test selectors and retained scope/budget authority. Default
  reconstructed continuity; persistent author sessions remain configurable.
- Prove these routes through existing campaign/replenishment controllers,
  including eligible siblings, data deferrals, exhausted authority, duplicate
  delivery, restart, and changed-condition reconsideration.
- Render and browser-test the complete Mission Control episode state, including
  method/review stages, owner, recovery condition, budgets and unknown usage.

No live model calls, campaigns, mandates, orders, or deployment were performed by
this increment. The implementation is a prerequisite safety repair, not an
end-to-end autonomy certificate or completion of AEP-007.

Verification: 205 focused worker tests and 11 backend provider-circuit tests
passed. Backend tests use mocked database access and a non-secret placeholder
for import-time configuration. No production credentials or database were used.
Changes remain local and undeployed. Rollout must install the additive permit
revision field before relying on automatic episode capacity recovery; an older
API without a revision cannot authorize that recovery.

## Method-task publication increment

`MethodTaskContract`, `AlphaMethodDesignExecutor` and the `alpha-method-designer`
package connect AEP-004 to the existing restricted worker. A dedicated capability
and digest-pinned workflow are required. No existing agent receives that capability
or new authority automatically. The configured native validation environment is
required; the adapter does not install dependencies or modify Bulletproof.

A new campaign can include exact `method_design_requests` keyed by candidate ID.
They are part of its frozen specification and require explicit founder activation
for this commissioning phase. Director activation cannot select this uncommissioned
path. Old campaigns and tasks are not migrated. The campaign director materializes
a content-addressed child of the completed draft, with a campaign lock, immutable
contract comparison and no mandate-counter reset. It rechecks the source, candidate,
mandate and expiry on every reconciliation, including duplicate delivery.

Method tasks participate in drain pause, provider circuits and normal task leases.
Leasing requires a registered producer identity; start and heartbeat check current
mandate authority. The executor checks missing native design fields deterministically,
uses bounded correction only when needed, and checks provider capacity before a
model-call reservation. Native diagnostics use the pinned CLI and verified receipts.
Periodic lease heartbeats and cancellation surround both model and native work.

An operationally succeeded task means its result was retained, not that its method
was approved. The campaign verifies result/source/contract/budget bindings, unchanged
scientific identity, allowed method fields, native receipt custody and the exact
review packet. A ready packet is published once as `method_packet_published`, with
lease-time producer identity. It stops at `await_independent_method_review`; it
cannot fall through to legacy approval or engineering. A deferred method follows
the existing zero-trial candidate-deferral path so an eligible sibling can advance.

This increment does not yet materialize AEP-005 reviewer tasks from that publication.
No author session is exposed to reviewers. Native diagnostic readiness explicitly
retains the need for independent review and calibration; it is not evidence that
those checks passed. This is local integration, not a deployed or commissioned loop.

Increment verification: 192 backend tests and 158 worker tests passed, covering
campaign dispatch, idempotent task/packet publication, authority revocation,
schema parity, fixed-workflow/package validation, provider deferral, worker service,
controls and the existing method/engineering episode regressions. Native transport
is stubbed in the new executor tests; these are not genuine-candidate or live-model
commissioning receipts. No deployment or new agent registration was performed.
