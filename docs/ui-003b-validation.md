# UI-003B Canonical Knowledge Graph Explorer

## Implemented boundary

Mission Control now exposes the RI-008 projection as an interactive, read-only graph
workspace. The local API accepts only typed neighborhood, path or subgraph parameters
and forwards them to `/v1/research/graph/query`. Queries are capped at 100 visible
nodes, depth five and the canonical predicate vocabulary. The interface cannot create
edges, rebuild projections, mutate evidence or execute work.

The explorer shows projection and query digests, bounded/truncated state, categorical
node shapes, predicate-specific edge styles, selected-node identity and visible
neighbors. A selected node can issue a bounded neighborhood query or replay canonical
evidence through the same coordinate-replay boundary used by UI-003A. Copilot
citations can open directly into this graph state.

## Founder experience

Desktop presents an SVG relationship map with zoom and fit controls beside a compact
evidence inspector. The deterministic layout avoids a new client dependency and
renders at most 100 nodes. The relationship view is an adjacency list with native
buttons and explicit predicate labels; it is the default on mobile and the accessible
source of truth. Node type is encoded by shape and label as well as color, while
`supports` and `contradicts` use distinct solid and dashed edge treatments.

## Verification

- Mission Control tests: 65 passed.
- Ruff, compileall and JavaScript syntax: passed.
- Typed query forwarding and executable-field rejection: passed.
- Desktop inspection: 1440 by 1100, no overlap or console errors.
- Mobile inspection: 390 by 844, readable controls and keyboard adjacency.
- Canonical replay remains read-only and credential-free in the browser response.

## Production gate

After commit and Mac reinstall, acceptance requires one current-projection overview,
one bounded neighborhood expansion and exact replay of a selected canonical object.
The returned corpus/query digests and object identity must be retained below before
UI-003B is described as production-observed.
