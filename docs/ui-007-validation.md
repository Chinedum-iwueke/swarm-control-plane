# UI-007 Integrated Conversation Workspace Validation

## Delivered boundary

UI-007 turns the OPS-006 founder thread into one operational work surface. Mission
Control now joins the canonical conversation transcript and live specification with
its planner proposals, materialized tasks, approvals, task events and digest-bound
artifacts. The join is read-only and follows stored conversation and task identities;
the browser does not infer execution state.

The workspace supports new-thread creation without browser prompts, cross-channel
message provenance, thread switching, continuation, finish, stop and resume. Proposed
work links to the existing governed proposal-review surface. Task and artifact rows
open bounded inspectors with lifecycle, result and provenance details.

## Authority and safety

- Conversation turns remain intent, not execution authority.
- Proposal review and approval continue through their existing protected mutations.
- The workspace endpoint creates no state and grants no permission.
- Evidence is displayed from registered artifacts and retains SHA-256, workflow,
  source-commit and verification metadata.
- Demo mode remains mutation-disabled and isolated from the control plane.

## Automated evidence

- Backend suite: 295 tests passed.
- Mission Control suite: 68 tests passed.
- Changed Python passed Ruff.
- Mission Control JavaScript passed `node --check`.
- Desktop and 390-pixel responsive layouts were exercised with the local browser
  against demonstration entities covering transcript, proposal, completed task and
  verified evidence states.

## Production qualification

Source implementation is complete. Production qualification requires merging this
change, deploying the API to VM2, reinstalling Mission Control on the Mac and replaying
one thread that begins on Telegram, continues in Mission Control, reaches proposal
review and exposes its eventual task evidence in the same workspace.

