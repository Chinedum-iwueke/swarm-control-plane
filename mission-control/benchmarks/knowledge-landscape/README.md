# Knowledge Landscape Real-Data Benchmark

This benchmark validates the bounded Knowledge Landscape contract against the
canonical production graph without modifying the deployed API or graph state.

## Snapshot

- Measured: 2026-11-12 UTC
- Corpus: 784,270 nodes and 1,368,847 edges
- Request bound: 100 nodes and 240 edges
- Returned: 100 real canonical nodes and 121 real projected edges
- Visible categories: claim, dataset, decision, edition, episode, result,
  review, run, and source
- Selection: 53 scientific-lifecycle nodes, 24 sources, and 23 editions
- Median latency: 530.83 ms
- p95 latency: 646.49 ms
- Maximum latency: 686.23 ms

The previous generic overview returned the first 100 `scientific_object` nodes
and no edges. The representative landscape now exposes nine meaningful object
types and connected provenance while retaining the same 100-node response
ceiling. An early unoptimized landscape candidate took 4,870.63 ms; the
authorization-aware aggregate fast path reduced the measured warm p95 to
646.49 ms across 20 measured trials.

The response remains intentionally truncated. It reports the full corpus and
facet counts, selection strategy, visible limits, and truncation reasons so the
sample cannot be mistaken for the whole institutional graph.

## Reproduce

Run the benchmark in an environment with read-only access to the canonical
graph database:

```bash
python -m app.pilots.knowledge_landscape_benchmark \
  --warmups 2 \
  --trials 20 \
  --max-nodes 100 \
  --max-edges 240
```

The benchmark validates every response against `GraphLandscapeResponse`. It
does not rebuild the projection, mutate evidence, or invoke trading systems.

The captured machine-readable result is in `result.json`. Because the corpus
is live and append-only, future runs should be retained as dated snapshots
rather than overwriting historical measurements silently.

## Renderer verification

The retained SVG renderer was exercised in headless Chrome at the production
boundary with 100 representative nodes and 121 projected edges. Twenty cold
layouts and twenty warm rerenders produced:

- Cold layout: 36.5 ms median, 52.8 ms p95, 72.5 ms maximum.
- Warm rerender: 11.45 ms median, 20.0 ms p95, 20.2 ms maximum.
- Keyboard-addressable nodes: 100 of 100.
- Deterministic layout: confirmed from identical node and edge signatures.
- Responsive width: no document overflow at a 390 px viewport.

Category filtering, visual/list switching, zoom controls, and arrow-key node
traversal were also exercised in the browser. A separate, explicitly labelled
synthetic demonstration fixture verified evidence focus without making a
scientific-data claim: direct relations remained emphasized, four unrelated
nodes and four unrelated edges dimmed, the explicit `derived_from` relation was
labelled, fit-to-selection centered the record at 1.55x, and keyboard traversal
remained active. The exact captured measurements are retained in
`renderer-result.json`.
