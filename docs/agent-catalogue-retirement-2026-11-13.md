# Agent catalogue retirement: 2026-11-13

## Scope and evidence

Founder requested catalogue cleanup before resuming autonomous certification.
Inspected all 29 production agent registrations, package deployments, assigned
tasks (paginated), VM1/VM2 systemd services, and legacy evaluator assignments.
No model calls, backtests, trading actions, or autonomy-state changes were made.

Retirement uses the existing agent revoke API and package deployment revoke API,
not deletion. Agent status becomes `revoked`, `is_enabled=false`, and active
credentials are revoked. Historical tasks, receipts, reviews, profiles, packages,
and identities remain for provenance. Disabled agents cannot authenticate through
`get_current_agent` or qualify for evaluator routing. Retained profile records
are not a claim of current reviewer availability.

## Retired registrations

| Agent slug | Disposition rationale |
| --- | --- |
| vm2-lifecycle-validator | Never heartbeated, no package deployment, no unfinished assigned work or observed service. Retired unused registration, not a claim that lifecycle validation is unnecessary. |
| vm1-m13-senior-research-specialist | Legacy M13 registration; current supervised senior researcher is vm1-alpha004-senior-researcher. |
| vm1-m13-experiment-specification | Legacy M13 registration without a heartbeat/service; current representation and strategy-engineering roles handle the new pipeline. |
| vm1-m13-research-execution | Last heartbeat August 1; current research runner and capacity executors are retained. |
| vm1-m13-statistical-reviewer | No runtime heartbeat/service; both recorded evaluator assignments completed. Retirement does not certify equivalent statistical-review coverage in the new pipeline. |
| vm1-m13-adversarial-auditor | No runtime heartbeat/service; both recorded evaluator assignments completed. Current causality/spec reviewers remain, without implying identical coverage. |
| vm1-research-intelligence-director | Unused historical registration; current supervised director is vm1-alpha004-research-intelligence-director. |
| vm1-alpha-research-executor | First-generation executor last heartbeated September 10, service disabled; active capacity executors replace it. |

Before mutation, each selected agent had either no heartbeat or one older than
30 days, and no assigned task outside succeeded/failed/cancelled/rejected.
Heartbeat timestamps were rechecked immediately before revocation.
All four legacy reviewer assignments and their routes were completed.
Six active deployments were revoked; the other two agents had none.

## Retained exceptions and active roles

- `vm1-alpha-research-executor-v2` is NOT obsolete: its identity still heartbeats
  from a capacity executor. Its old standalone service being disabled is not
  grounds to revoke the identity.
- VM1, VM2 and VPS1 fleet observers remain enabled. Fleet observations are a
  separate reporting path; absent worker heartbeats alone do not justify removal.
- The operational-memory steward remains registered as an on-demand capability.
- The older VM2 infrastructure operator remains pending service/credential
  ownership investigation, not falsely declared redundant with the broker.
- The generic VM1 developer-coder remains registered. Its primary and four
  replica service units are failed, not proven superseded for all engineering.
  Repair/disable decisions for those services remain separate work.
- Current research runner, founder planner, deployment architect, research memory
  steward, ALPHA004 director/researcher, both capacity executors, data admission,
  representation scientist, strategy engineer and independent spec/causality
  reviewers remain enabled. No active service was stopped.
- EXEC1 and EXEC2 observer identities were already revoked and remain historical.

## Verification and limits

Post-mutation API readback: 29 historical registrations, 19 enabled, 10 revoked.
All eight selected identities are disabled/revoked; every other agent's enabled
flag is unchanged. No record was deleted. No new successful scientific or
autonomy certification is inferred from catalogue cleanup.

Implementation references: `backend/app/api/routes/agents.py::revoke_agent`,
`backend/app/api/routes/packages.py::revoke_deployment`,
`backend/app/core/security.py::get_current_agent`, and
`backend/app/services/evaluator_routing.py` enabled-agent selection.
