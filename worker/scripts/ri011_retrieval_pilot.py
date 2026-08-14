from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

CURRICULUM_ID = "6470d401-da23-440c-8c48-42d3820b7614"
PROJECTION_VERSION = "hybrid-retrieval-v1.1.0"
WARM_P95_SLO_MS = 2_000.0
CONCURRENT_P95_SLO_MS = 5_000.0
CASES = [
    {
        "case_key": "commodity-momentum-evidence",
        "query": "What does the evidence say about commodity momentum and trend following?",
        "expected_object_ids": ["d98c71ca-bf52-567d-9b35-e23411f561a5"],
        "opposing_object_ids": [],
        "forbidden_object_ids": [],
        "should_abstain": False,
    },
    {
        "case_key": "unknown-private-strategy",
        "query": "What is the Sharpe ratio for private strategy HERMES-ZQX-999-2049?",
        "expected_object_ids": [],
        "opposing_object_ids": [],
        "forbidden_object_ids": [],
        "should_abstain": True,
    },
]


def request(
    client: httpx.Client,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def rebuild(client: httpx.Client) -> dict[str, Any]:
    return request(client, "POST", "/v1/research/retrieval/projections/rebuild")


def benchmark(client: httpx.Client) -> dict[str, Any]:
    evaluations = request(
        client,
        "GET",
        f"/v1/research/curricula/{CURRICULUM_ID}/evaluations",
    )
    next(item for item in evaluations if item["passed"])
    cases = CASES

    def run_case(case: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        result = request(
            client,
            "POST",
            "/v1/research/retrieval/query",
            {
                "query": case["query"],
                "projection_version": PROJECTION_VERSION,
            },
        )
        elapsed = (time.perf_counter() - started) * 1_000
        returned = {item["object_id"] for item in result["hits"]}
        expected = set(case.get("expected_object_ids", []))
        correct = (
            result["abstained"]
            if case.get("should_abstain")
            else bool(returned & expected)
        )
        return {
            "case_key": case["case_key"],
            "elapsed_ms": round(elapsed, 3),
            "server_timings_ms": result["timings_ms"],
            "candidate_counts": result["candidate_counts"],
            "correct": correct,
        }

    run_case(cases[0])
    warm = [run_case(case) for case in cases for _ in range(2)]
    with ThreadPoolExecutor(max_workers=min(4, len(cases))) as pool:
        concurrent = list(pool.map(run_case, cases))
    warm_latencies = [item["elapsed_ms"] for item in warm]
    concurrent_latencies = [item["elapsed_ms"] for item in concurrent]
    report = {
        "projection_version": PROJECTION_VERSION,
        "curriculum_id": CURRICULUM_ID,
        "case_count": len(cases),
        "warm": {
            "p50_ms": percentile(warm_latencies, 0.50),
            "p95_ms": percentile(warm_latencies, 0.95),
            "maximum_bounded_candidates": max(
                item["candidate_counts"]["bounded"] for item in warm
            ),
            "correct": all(item["correct"] for item in warm),
        },
        "concurrent": {
            "workers": min(4, len(cases)),
            "p95_ms": percentile(concurrent_latencies, 0.95),
            "correct": all(item["correct"] for item in concurrent),
        },
        "slo": {
            "warm_p95_ms": WARM_P95_SLO_MS,
            "concurrent_p95_ms": CONCURRENT_P95_SLO_MS,
        },
        "cases": warm,
    }
    report["passed"] = bool(
        report["warm"]["correct"]
        and report["concurrent"]["correct"]
        and report["warm"]["p95_ms"] <= WARM_P95_SLO_MS
        and report["concurrent"]["p95_ms"] <= CONCURRENT_P95_SLO_MS
    )
    report["report_digest"] = digest(report)
    return report


def evaluate(client: httpx.Client, version: str) -> dict[str, Any]:
    evaluations = request(
        client,
        "GET",
        f"/v1/research/curricula/{CURRICULUM_ID}/evaluations",
    )
    qualified = next(item for item in evaluations if item["passed"])
    return request(
        client,
        "POST",
        f"/v1/research/curricula/{CURRICULUM_ID}/evaluations",
        {
            "curriculum_id": CURRICULUM_ID,
            "evaluation_version": version,
            "cases": CASES,
            "thresholds": qualified["thresholds"],
            "evaluated_by": "ri011-independent-evaluator",
        },
    )


def percentile(values: list[float], quantile: float) -> float:
    if len(values) == 1:
        return round(values[0], 3)
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 3)


def digest(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("rebuild", "benchmark", "evaluate"))
    parser.add_argument("--evaluation-version", default="1.0.2")
    args = parser.parse_args()
    api_url = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    timeout = 1_800 if args.command == "rebuild" else 120
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    ) as client:
        if args.command == "rebuild":
            result = rebuild(client)
        elif args.command == "benchmark":
            result = benchmark(client)
        else:
            result = evaluate(client, args.evaluation_version)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
