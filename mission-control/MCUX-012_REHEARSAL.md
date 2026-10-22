# MCUX-012 Investor Walkthrough Rehearsal

**Status:** instrumented contract rehearsal complete; moderated unfamiliar-user
validation remains a release gate in MCUX-024.
**Rehearsed:** 2026-10-22
**Path:** Command status -> active workflow -> responsible agent -> terminal
BT-009 backtest -> Bybit demo event.

## Evidence boundary

The walkthrough projection selects only records returned by the current
dashboard, workflow, backtest and EXEC-011 event projections. A missing link is
rendered `unavailable`; it is never replaced with demonstration data, a
successful engineering task or a nearby event from another account. The
isolated `?demo=1` interface explicitly refuses to start or retain an investor
rehearsal.

This engineering rehearsal used deterministic canonical-contract fixtures to
exercise all five ready steps and incomplete-path fixtures to exercise missing
agent, receipt and event evidence. It did not involve an unfamiliar investor
and does not claim observed human comprehension. Production task time,
questions and misunderstandings will be written by the walkthrough journal
during the moderated MCUX-024 session.

## Instrumented record

Each rehearsal is bound to a SHA-256 digest of the selected walkthrough. The
local journal records:

- session start, terminal status and total elapsed milliseconds;
- ready and total step counts at start;
- each evidence-open and step-complete time;
- visitor questions, misunderstandings and evidence gaps with the active step;
- a terminal summary, including abandoned sessions.

The journal is bounded to 100 sessions and 250 observations per session, is
written atomically with mode `0600`, and is explicitly local usability evidence,
not canonical research or execution evidence.

## Findings And Fixes

| Engineering rehearsal finding | Retained correction |
|---|---|
| A successful task could be mistaken for a completed backtest. | The backtest step requires `native_terminal_receipt`, a present receipt and a digest. Otherwise the step is unavailable. |
| A workflow could appear to have an owner without a linked executing agent. | The agent step resolves only the selected leaf task's canonical `assigned_agent_id` or an explicit agent owner. Missing linkage is disclosed. |
| Reused correlation IDs could join events from separate venue accounts. | Demo lifecycle selection and inspector navigation require the same venue, environment and account pseudonym. |
| Illustrative demo fixtures looked visually complete enough to be mistaken for rehearsal evidence. | Demo mode refuses session creation and displays “Canonical evidence required.” |
| A stale browser could start a rehearsal against changed evidence. | Session creation reprojects the path and rejects a mismatched walkthrough digest with HTTP 409. |
| A guided path could hide how far the visitor had progressed. | The coach shows an explicit step number and progress bar and retains incomplete/abandoned sessions. |
| Small coach controls were difficult touch targets on mobile. | Coach actions and close/launch controls use a minimum 44px target; the layout collapses to one column at 680px. |

## Verification

- Projection tests cover a complete five-step chain, absent links and
  cross-account event isolation.
- API tests cover projection retrieval, stale-digest rejection, observation
  persistence, terminal session persistence and recent-session retrieval.
- UI tests cover every evidence route, truthful demo/unavailable language,
  progress instrumentation, responsive behavior and reduced motion.
- Chromium desktop and 390px mobile renders verified the deep-linked coach and
  demo-mode evidence boundary without overlap.

The source/reader, graph and conversation portions of the full investor script
are intentionally outside this bounded rehearsal. They remain gated on
MCUX-013 through MCUX-020 and the complete MCUX-023/024 release rehearsal.
