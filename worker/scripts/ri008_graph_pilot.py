#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx


def request(
    client: httpx.Client, method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise TypeError(f"{path} did not return an object")
    return value


def main() -> int:
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN", "")
    if not api_url or len(token) < 20:
        print("SWARM_API_URL and SWARM_ORCHESTRATOR_TOKEN are required.", file=sys.stderr)
        return 2
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=600,
    ) as client:
        projection = request(
            client, "POST", "/v1/research/graph/projections/rebuild", {}
        )
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
    result = {
        "projection": projection,
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
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
