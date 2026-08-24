# UI-007 Conversation Workspace Runbook

## Purpose

Verify the founder can follow one canonical job from conversation through governed
execution and evidence without confusing discussion with permission.

## Deployment

1. Deploy the control-plane API revision and recreate the healthy API container. No
   database migration is required for UI-007.
2. Reinstall Mission Control from the same source revision and restart its LaunchAgent.
3. Confirm `GET /v1/conversations/{id}/workspace` appears in the live OpenAPI document.

## Live acceptance

1. Start a named Telegram thread and add one follow-up turn.
2. Open Chat & Work in Mission Control and select the same short thread ID.
3. Confirm both turns retain their original channel provenance.
4. Continue the thread from Mission Control and review the compiled specification.
5. Open the linked proposal from the work timeline and use the existing governed
   review flow. Do not approve a proposal that still requires clarification.
6. After materialization and execution, verify task events appear chronologically and
   each registered artifact opens with its digest and source commit.
7. Finish the thread, confirm the composer is disabled, resume it and confirm a new
   turn can be accepted.

Retain the conversation ID, proposal digest, task number, artifact digest and API/Mac
source revisions as the production validation receipt.

## Rollback

Reinstall the preceding Mission Control revision and roll the API image back to the
preceding healthy revision. The canonical conversations, proposals, tasks, approvals
and artifacts remain intact because UI-007 adds a read model and user interface only.
