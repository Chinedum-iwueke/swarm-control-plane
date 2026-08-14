#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 1800.0


def request(
    client: httpx.Client, method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise TypeError(f"{path} did not return an object")
    return value


def ensure_current_projection(client: httpx.Client) -> tuple[dict[str, Any], bool]:
    try:
        projection = request(
            client, "GET", "/v1/research/graph/projections/status"
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in {404, 409}:
            raise
        projection = {}
    if projection and not projection.get("stale", True):
        return projection, False
    return (
        request(client, "POST", "/v1/research/graph/projections/rebuild", {}),
        True,
    )


def run_pilot(client: httpx.Client) -> dict[str, Any]:
    projection, projection_rebuilt = ensure_current_projection(client)
    overview = request(client, "GET", "/v1/research/graph/overview")
    tool = request(
        client,
        "POST",
        "/v1/research/graph/tools/execute",
        {"tool": "mean", "values": [1, 2, 3], "parameters": {}},
    )
    replayed = []
    for node in overview.get("nodes", [])[:3]:
        replay = request(client, "GET", node["replay_path"])
        if replay.get("content_digest") != node.get("content_digest"):
            raise RuntimeError("Graph node did not replay to its canonical digest")
        replayed.append(node["id"])
    return {
        "projection": projection,
        "projection_rebuilt": projection_rebuilt,
        "overview": {
            "query_digest": overview["query_digest"],
            "nodes": len(overview.get("nodes", [])),
            "edges": len(overview.get("edges", [])),
            "truncated": overview.get("truncated", False),
        },
        "sampled_replay_object_ids": replayed,
        "tool_receipt": {
            "receipt_id": tool["receipt_id"],
            "receipt_digest": tool["receipt_digest"],
            "result": tool["result"],
        },
    }


def main() -> int:
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN", "")
    if not api_url or len(token) < 20:
        print("SWARM_API_URL and SWARM_ORCHESTRATOR_TOKEN are required.", file=sys.stderr)
        return 2
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=DEFAULT_TIMEOUT_SECONDS,
    ) as client:
        result = run_pilot(client)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
