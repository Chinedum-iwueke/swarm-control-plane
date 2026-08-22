# UI-003C Integrated Research Workspace

## Implemented boundary

Mission Control now integrates the proven UI-003A Copilot and UI-003B graph explorer
with source management in one research workspace. The three modes are `Ask`, `Explore`
and `Library`; each has a URL-restorable state and retains its local interaction state
when another mode is opened. No new control-plane mutation, model authority, graph
authority or evidence authority was introduced.

A shared working-context strip holds at most eight selected canonical identities.
Opening a citation or explicitly selecting a graph node adds its ID, type and digest.
The context is browser-session navigation state, not a context-pack override, canonical
collection, saved conversation or institutional-memory write. Opening an item returns
to its canonical inspector or bounded graph neighborhood.

## Founder experience

The workspace begins with compact projection, visible-graph, curriculum and ingestion
attention indicators. Semantic tabs separate synthesis, relationship inspection and
corpus operations without sending the founder to different product areas. Arrow, Home
and End keys move focus and selection across the tabs. The same panels become a
single-column surface on mobile, with scrollable context items and touch-sized actions.

## Verification

- Mission Control tests: 65 passed.
- Ruff, compileall, JavaScript syntax and diff checks: passed.
- Desktop inspection: 1440 by 1100; all three modes fit without overlap.
- Mobile inspection: 390 by 844; Library controls remain readable without horizontal
  page overflow.
- Semantic tab roles, labels, selection and URL restoration: observed.
- Graph panel hide/restore and selected-node context carryover: observed.
- Browser console: no errors.

## Production gate

After commit and Mac reinstall, acceptance requires the live workspace status to show
the current canonical graph, a Copilot citation to enter working context, the same
object to open as a bounded graph root, and exact replay to remain available. Retain
the live object, corpus and query digests below before describing UI-003C as
production-observed.
