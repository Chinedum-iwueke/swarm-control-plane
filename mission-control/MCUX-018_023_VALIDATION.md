# MCUX-018 through MCUX-023 Validation

Date: 2026-10-24

## Claim Boundary

MCUX-018 through MCUX-022 are engineering-complete when the checks below pass
against the deployed build. MCUX-023 is not investor-readiness qualified until
MCUX-024 records the required moderated founder and first-time investor test.
Technical rollout is necessary evidence, not a substitute for that human gate.

## Shipped Contract

- `GET /v1/conversations/{id}/work-events` projects only persisted conversation
  messages/events, proposals, tasks/task events, approvals/approval events,
  artifacts and founder notifications. Each item identifies its source record,
  thread, optional task, timestamp and opaque replay cursor.
- Reconnect requests use `after`; stable event IDs are deduplicated in the
  browser. There are no fabricated assistant chunks, percentages, tool calls or
  progress states.
- The workbench retains its selected thread, supports open/archive/all search,
  polls independently of the chat request, shows structured work/evidence and
  does not move scroll position when background events arrive.
- Telegram and Mission Control messages share the canonical conversation and
  reply ancestry records. Delivery notifications appear in the same work-event
  stream. Resend invokes governed approval rearm, which creates no task and
  grants no approval or extended authority.
- Approval views separate actionable, blocked, expired, decided and superseded
  records. The decision sheet exposes the exact plan/review digests, risk,
  scope, prerequisites, expected outputs, bounded effect and expiry. Cancel and
  close buttons bypass incomplete form validation.

## Automated Checks

Run from the repository root:

```bash
POSTGRES_PASSWORD_FILE=/etc/hostname \
  backend/.venv/bin/python -m pytest backend/tests/test_founder_conversations.py -q
mission-control/.venv/bin/python -m pytest mission-control/tests -q
node --check mission-control/src/hermes_mission_control/static/app.js
```

The Mission Control suite includes explicit keyboard/screen-reader landmarks,
reduced-motion and responsive contracts, cursor deduplication, scroll retention,
API failure messaging and fixed static-asset budgets. A service worker is
deliberately absent so stale cached authority state cannot survive a release.

Chromium QA loaded `?view=work&demo=1` at 375x812, 768x1024 and 1280x720.
The accessibility tree exposed skip navigation, thread search/tabs, messages,
composer, work events and evidence as keyboard controls; the console was empty
and no text overlap was visible at any viewport. Asset identities for this
candidate are:

- `app.js`: `05e769114152bdcf03b2e662e4f0924f7e7b77b2428d8f3d9d8e74f59a7a7a4b`
- `styles.css`: `5e52ea5e47935b39085d99d8e2941bf8582a5a5ca0b49d66058eebbb2a0891c2`
- `index.html`: `8a073debad09359f63e44fc222e691f11b41ae51413597a651a5d93750e9df27`

## Release And Rollback

1. Push the reviewed commit to `origin/main`.
2. On VM2, fast-forward the runtime checkout, rebuild the API image, run Alembic
   to head, recreate `api`, and verify `/health` plus the protected work-event
   route.
3. On the Mac, fast-forward the checkout, run `mission-control/macos/install.sh`,
   restart the launch agent, and verify the loopback health and static asset.
4. Record the deployed commit and image digest in the rollout output.
5. Roll back by checking out the prior recorded commit in both runtime checkouts,
   rebuilding/reinstalling with the same commands, and repeating health checks.
   This release adds no database migration, so rollback does not require data
   reversal.

## Remaining Release Gate

MCUX-024 must still observe one unfamiliar founder-operator and one unfamiliar
investor completing the canonical walkthrough without shell access or
engineering narration. MCUX-023 remains open until that report exists and any
critical findings are remediated.
