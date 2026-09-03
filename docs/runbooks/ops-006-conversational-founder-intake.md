# OPS-006 Conversational Founder Intake

## Conversational intelligence hardening

Founder-intake planning is repository-neutral: a project named in conversation is
context, not repository execution authority. The planner first performs a bounded,
read-only reasoning pass over the ordered conversation plus supplied Research
Intelligence hits, dataset manifests, hypothesis records and active task
capabilities. Questions may be answered directly. Only an explicit executable
intent advances into the separately schema-constrained proposal compiler.

Queued work denied by effective authority records `task_authority_denied` with its
reasons. A leased task moves its conversation to `planning`; a current revision
that does not advance within two minutes becomes `attention_required` and emits a
deduplicated founder alert. Telegram renders both planning and stalled notices,
while Mission Control polls active Chat & Work state every ten seconds.

## Contract

Founder requests from Telegram and Mission Control are persisted as canonical
conversation threads. A turn records its channel, immutable digest, sequence, and
conversation revision. Later turns refine the same job; they do not create unrelated
founder requests. Telegram and Mission Control use the same `founder:primary` identity.

Every turn creates a bounded planner task containing the ordered recent transcript,
the current project classification, deterministic administrative identifiers, and a
domain specification guide. An unstarted older planning revision is cancelled. A
running older revision may finish, but the API rejects its proposal as superseded.
Only the latest digest-bound proposal may be materialized.

The planner may apply documented, non-safety-critical defaults when the founder asks
for reasonable choices. Each decision records the field, value, basis, policy version,
confidence, and considered alternatives. It may never default scientific meaning,
unavailable data, permission expansion, credentials, live trading, or production
promotion. A clarification must name every unresolved field and give its accepted
format and an example.

## Telegram

- Plain English starts a thread when none is selected and otherwise continues it.
- `/new [title]` starts a new job with the next message.
- `/threads` lists recent threads.
- `/context` displays the selected thread and unresolved fields.
- `/switch <short-id>` changes the open thread.
- `/finish` closes completed work; `/stop` halts it.
- `/resume <short-id>` reopens a finished or stopped thread.

No Telegram message contains credentials, shell commands, or direct execution
authority. Proposal review and task approval remain separate governed transitions.

## Mission Control

The **Chat & Work** workspace lists canonical threads, shows the cross-channel
transcript and live structured specification, accepts follow-up turns, and exposes
finish/stop controls. Proposal approval continues through the existing proposal
inspector after the planner has produced an executable specification.

## Deploy

1. Apply Alembic revision `c2f8a6d41e90` and recreate the VM2 API.
2. Reinstall the VM1 founder planner package and deploy its new attestation.
3. Reinstall and restart the VM1 Telegram gateway.
4. Reinstall Mission Control on the Mac and restart its LaunchAgent.
5. Replay the validation transcript before accepting production traffic.

## Rollback

Stop the planner and Telegram gateway before rolling the API back. Preserve all
conversation, message, event, proposal, and task rows as audit evidence. The migration
downgrade is allowed only before any OPS-006 conversation is accepted; otherwise ship
a forward-compatible corrective migration.
