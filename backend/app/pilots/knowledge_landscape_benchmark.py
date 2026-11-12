from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import UTC, datetime
from typing import Any

from app.db.session import SessionLocal
from app.schemas.graph import GraphLandscapeRequest, GraphLandscapeResponse
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.graph import graph_landscape


def run_benchmark(
    *, trials: int, warmups: int, max_nodes: int, max_edges: int
) -> dict[str, Any]:
    request = GraphLandscapeRequest(max_nodes=max_nodes, max_edges=max_edges)
    latencies: list[float] = []
    with SessionLocal() as db:
        for _ in range(warmups):
            graph_landscape(db, request, ORCHESTRATOR_ACCESS)
        payload: dict[str, Any] | None = None
        for _ in range(trials):
            started = time.perf_counter()
            payload = graph_landscape(db, request, ORCHESTRATOR_ACCESS)
            latencies.append((time.perf_counter() - started) * 1000)
    assert payload is not None
    validated = GraphLandscapeResponse.model_validate(payload)
    ordered = sorted(latencies)
    p95_index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1))
    return {
        "schema_version": "knowledge-landscape-real-data-benchmark-v1.0.0",
        "measured_at": datetime.now(UTC).isoformat(),
        "trials": trials,
        "warmups": warmups,
        "request": {"max_nodes": max_nodes, "max_edges": max_edges},
        "corpus": {
            "nodes": validated.corpus_node_count,
            "edges": validated.corpus_edge_count,
            "node_facets": [item.model_dump() for item in validated.node_facets],
            "edge_facets": [item.model_dump() for item in validated.edge_facets],
        },
        "visible": {
            "nodes": len(validated.nodes),
            "edges": len(validated.edges),
            "node_types": sorted({item.object_type for item in validated.nodes}),
            "selection": validated.selection.model_dump(),
            "truncated": validated.truncated,
            "truncation_reasons": validated.truncation_reasons,
        },
        "latency_ms": {
            "minimum": round(min(ordered), 2),
            "median": round(statistics.median(ordered), 2),
            "p95": round(ordered[p95_index], 2),
            "maximum": round(max(ordered), 2),
            "samples": [round(item, 2) for item in latencies],
        },
        "query_digest": validated.query_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the read-only knowledge landscape on canonical data."
    )
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--max-nodes", type=int, default=100)
    parser.add_argument("--max-edges", type=int, default=240)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.trials < 1 or args.warmups < 0:
        parser.error("trials must be positive and warmups must be non-negative")
    report = run_benchmark(
        trials=args.trials,
        warmups=args.warmups,
        max_nodes=args.max_nodes,
        max_edges=args.max_edges,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
