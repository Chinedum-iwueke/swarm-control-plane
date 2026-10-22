# MCUX-016 Graph Renderer Decision

**Decision date:** 2026-10-22
**Production limit:** 100 visible nodes, 240 visible edges
**Decision:** Retain the dependency-free SVG renderer for the bounded Mission
Control explorer. Do not add Cytoscape.js or a WebGL renderer yet.

## Method

The retained harness in `benchmarks/graph-renderers` generates deterministic
25, 100 and 250-node fixtures with tree and cross edges. It runs 25 trials per
case in Chrome 146 and compares DOM construction, filter/path-class dispatch,
deterministic positions, keyboard exposure and gesture support. The 250-node
case is deliberately above the production cap. Run it with:

```bash
mission-control/benchmarks/graph-renderers/run.sh
```

The script downloads the pinned Cytoscape.js 3.34.4 benchmark dependency into a
temporary directory; the library is not shipped in Mission Control. Exact
measured output is retained in `result.json`.

## Result

At the 100-node production boundary, SVG setup was 3.0 ms and interaction-class
dispatch was 0.2 ms. Cytoscape setup was 9.3 ms and dispatch was 0.4 ms. Both
kept deterministic preset positions. SVG exposed all 100 nodes as focusable
semantic elements; Cytoscape's canvas exposed none and would still require the
synchronized relationship list for accessible operation. Cytoscape provided
native pinch zoom and a much smaller DOM, but neither advantage is material at
the enforced 100-node limit. The current SVG supports pointer pan, wheel/button
zoom and node drag. Mobile users retain touch-sized zoom/fit controls and the
complete relationship list rather than depending on a gesture.

The 250-node stress fixture remained below 5 ms SVG setup on this host. That is
not permission to raise the API/UI cap; query authorization, readable density
and evidence freshness remain the limiting product constraints.

## WebGL Boundary

A WebGL comparison was not activated. Neither tested renderer approached the
50 ms interaction or 100 ms initialization budgets at the production boundary,
and no approved view may render more than 100 nodes. Re-open WebGL evaluation
only if a reviewed product requirement raises the visible-node contract above
500 or measured browser traces exceed those budgets on target Mac hardware.

This decision does not claim Obsidian parity. It selects a renderer for the
specific bounded evidence-navigation tasks in MCUX-017.
