#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise AGT-003 bounded task graphs.")
    parser.add_argument("--output", type=Path, default=Path("/var/lib/invariance-swarm/agt003/report.json"))
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/")
    base = base.removesuffix("/v1")
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    task = {
        "task_type": "agt003_noop_pilot",
        "title": "AGT-003 bounded no-execution pilot",
        "objective": "Retain a typed contract without performing external action.",
        "expected_outputs": ["typed-receipt.json"],
        "acceptance_criteria": ["No task is leased before founder cancellation."],
        "max_attempts": 1,
        "risk_level": 0,
    }
    manifest = {
        "graph_key": f"AGT003-PILOT-{stamp}",
        "project": "swarm-control-plane",
        "objective": "Prove typed messages, dependency gates, cancellation and replay without execution authority.",
        "created_by": "founder-operator",
        "max_nodes": 2,
        "max_total_attempts": 2,
        "max_duration_seconds": 300,
        "max_parallelism": 1,
        "nodes": [
            {"key": "specify", "role": "specification-agent", "input_type": "pilot.request.v1", "output_type": "pilot.specification.v1", "task": task, "stop_conditions": ["Founder cancels graph or lease is lost."]},
            {"key": "review", "role": "independent-reviewer", "node_type": "review", "depends_on": ["specify"], "input_type": "pilot.specification.v1", "output_type": "pilot.review.v1", "task": {**task, "title": "AGT-003 independent no-execution review"}, "stop_conditions": ["Upstream fails, founder cancels graph, or lease is lost."]},
        ],
    }
    with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
        created = client.post("/v1/task-graphs", json=manifest)
        created.raise_for_status()
        graph = created.json()
        graph_id = graph["id"]
        activated = client.post(f"/v1/task-graphs/{graph_id}/activate", json={"actor": "founder-operator", "reason": "Approved bounded pilot."})
        activated.raise_for_status()
        messaged = client.post(f"/v1/task-graphs/{graph_id}/messages", json={"node_key": "specify", "message_type": "pilot.request.v1", "sender": "founder-operator", "recipient": "specification-agent", "payload": {"request": "demonstrate cancellation before lease"}})
        messaged.raise_for_status()
        cancelled = client.post(f"/v1/task-graphs/{graph_id}/cancel", json={"actor": "founder-operator", "reason": "AGT-003 cancellation proof."})
        cancelled.raise_for_status()
        final = cancelled.json()["graph"]
    assert final["status"] == "cancelled"
    assert all(node["status"] == "cancelled" for node in final["nodes"])
    assert [item["sequence"] for item in final["events"]] == list(range(1, len(final["events"]) + 1))
    for previous, current in zip(final["events"], final["events"][1:]):
        assert current["previous_digest"] == previous["event_digest"]
    report = {
        "schema_version": "agt003-pilot-report-v1.0.0",
        "success": True,
        "graph_id": graph_id,
        "manifest_digest": final["manifest_digest"],
        "status": final["status"],
        "node_count": len(final["nodes"]),
        "message_digests": [item["payload_digest"] for item in final["messages"]],
        "event_chain_head": final["events"][-1]["event_digest"],
        "execution_authority": False,
        "capital_authority": False,
    }
    report["report_digest"] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
