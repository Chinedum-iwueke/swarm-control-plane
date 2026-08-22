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

## Production observation

Mission Control was installed and started on the Mac at commit `8c93afd`. Its live
current-projection overview returned 100 nodes and reported truncation. Expanding
scientific object `00001bd0-d136-5193-81d2-6016934a8a1e` with depth two and a
50-node cap returned 50 nodes and 50 edges under:

- projection `knowledge-graph-v1.0.0`;
- corpus digest `99888f190edc9b3c36481810570aa9c20deff6bddb0c6f6d7be31455ba4e0eb7`;
- query digest `66dfe123158bbab8022043eb08fd5d42bd935378218d2e004dc54e07744e01ef`.

Exact replay of canonical object `011a2e4b-25ff-572f-81f8-855433a2e961`
returned HTTP 200 with replay digest
`81d5566ea2770f49c7a5408927779fc9080e470530972706e51a969e1238bc1b`.
The corpus-scale replay took 91.95 seconds, so only the read-only replay call now has
a bounded 120-second timeout. Graph queries, mutations and all other control-plane
calls retain their existing bounds.
