# Conversational Intelligence Validation

## Scope

This hardening closes the August 29 founder-thread failure across OPS-006,
CHAN-002 and UI-007. It does not grant conversational models execution authority.

## Implemented guarantees

- Founder-intake planning is repository-neutral. A referenced project selects
  context but does not require or confer repository execution access.
- Effective-authority denial is recorded as a visible task event instead of being
  indistinguishable from an empty queue.
- Each accepted founder turn appears once in ordered context.
- Conversations expose `collecting`, `planning`, `needs_clarification`,
  `ready_for_review` and `attention_required` states.
- Planning older than two minutes produces a deduplicated founder notification,
  including effective-authority reasons when present.
- Grounded requests use a separate read-only reasoning stage before any proposal
  compiler is invoked.
- The reasoning stage receives bounded hybrid-retrieval evidence, registered
  datasets, registered hypotheses and enabled task capabilities. It may answer,
  request a genuinely blocking clarification, or request proposal compilation.
- Direct answers never contain a proposed task or approval action. Executable work
  still passes through the strict proposal schema and founder materialization.
- Telegram displays planning and stalled states. Mission Control refreshes active
  conversation work every ten seconds.

## Verification

- Backend suite: 642 passed.
- Founder planner tests: 13 passed.
- Telegram gateway suite: 41 passed.
- Mission Control suite: 72 passed.
- Ruff, Python compilation and whitespace checks pass for changed surfaces.

Production qualification additionally requires deployment of the API, planner,
Telegram gateway and Mission Control client, followed by successful processing of
the stranded August 29 conversation revision.

## Rollback

Roll back the application binaries together. Existing conversations, messages,
task authority events and notification receipts remain append-only evidence.
Disabling the planner prevents new reasoning or proposal generation without
altering already registered tasks or approvals.
