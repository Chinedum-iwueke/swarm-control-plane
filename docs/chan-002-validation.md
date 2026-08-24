# CHAN-002 Validation Record

**Date:** 2026-08-24
**Status:** Production validated

## Implemented

- Durable monotonic polling offset with post-success commit.
- Numeric update ordering and duplicate-update suppression.
- Persistent Telegram-message to canonical-conversation bindings.
- Reply-to thread selection across concurrent jobs and process restart.
- Fail-closed unknown and closed reply targets.
- Non-mutating, deduplicated handling of edited messages.
- Lossless bounded outbound message splitting with final-chunk review controls.
- Thread-bound clarification notifications with field and format guidance.
- Wrong-thread proposal approval refusal without prematurely consuming the handoff.
- Canonical reply metadata on OPS-006 conversation messages.
- Held-draft routing for ambiguous plain-English input with `/continue`, `/new`, and
  `/cancel`, without retyping or silently mixing jobs.
- Fifteen-minute conversational continuity for active Telegram threads.
- Typed daily-research notification bindings and pasted-card recognition.
- Planner prompt coverage for delegated choices: one numbered decision brief, one
  marked recommendation, number-only reply, and no false specialist attribution.

## Automated evidence

The Telegram suite covers sender allowlisting, the August 23 five-turn transcript,
restart offset recovery, out-of-order and duplicate updates, two concurrent threads,
reply override, clarification reply binding, edited messages, stale/non-executable and
wrong-thread approvals, expiration/single use, notification delivery acknowledgement,
delivery failure, actionable dependency gates, fleet alerts and long Telegram output.

The complete backend and Mission Control suites remain green with the extended
conversation response contract. Ruff, compileall and diff checks pass.

Validated totals:

- Telegram gateway: 32 passed.
- Control-plane backend: 294 passed.
- Mission Control: 67 passed.

## Production evidence

The VM2 API was migrated to `c2f8a6d41e90`, recreated from the current image and
verified healthy with all seven conversation routes. The VM2 Telegram gateway was
reinstalled and remained active with zero restarts after the replay.

The live two-thread restart replay retained two collecting conversations. Replying to
the older Alpha acknowledgement after a gateway restart selected Alpha and advanced it
from revision 1 to revision 2 exactly once. Replying to the Beta acknowledgement while
Alpha was selected returned to Beta and recorded one reply-bound turn. Canonical
evidence retained the Telegram message/reply references `343 -> 331` for Alpha and
`347 -> 336` for Beta. No credentials are present in this record.

One deliberately mis-sent ordinary message advanced Beta before the successful reply
test. It remains in canonical audit history rather than being rewritten or removed,
which is the intended immutable behavior.
