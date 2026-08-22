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

## Production observation

Mission Control was installed and started on the Mac at commit `a4267ed`. The shipped
page exposed all three workspace panels and the shared context surface. Canonical
Copilot citation `011a2e4b-25ff-572f-81f8-855433a2e961` was exercised as the same
graph root: a depth-one, 30-node-bounded query returned three nodes and two edges in
0.3 seconds under:

- projection `knowledge-graph-v1.0.0`;
- corpus digest `99888f190edc9b3c36481810570aa9c20deff6bddb0c6f6d7be31455ba4e0eb7`;
- query digest `5fe70dad7708a7c92621547ae7ce4ee2c9a6620337b21ef72fc0deafccb34562`.

Exact replay of that object returned HTTP 200 in 22.38 seconds with replay digest
`81d5566ea2770f49c7a5408927779fc9080e470530972706e51a969e1238bc1b`.
UI-003C is therefore production-observed without introducing a new mutation or model
authority path.
