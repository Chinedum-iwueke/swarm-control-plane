#!/usr/bin/env python3
"""Reconcile and replay one governed DISC-001 daily-question proposal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=120,
    ) as client:
        reconciled = client.post("/v1/research-programs/reconcile")
        reconciled.raise_for_status()
        cycles = reconciled.json()
        if not cycles:
            current = client.get("/v1/research-programs/cycles", params={"limit": 30})
            current.raise_for_status()
            cycles = [
                item
                for item in current.json()
                if item["status"] == "awaiting_brief"
                and item.get("digest", {}).get("selection", {}).get("schema_version")
                == "daily-research-selection-v1.0.0"
            ]
        if not cycles:
            raise RuntimeError("No DISC-001 proposal is awaiting founder review.")
        cycle = cycles[0]
        if args.approve and not cycle.get("digest", {}).get("approval"):
            decided = client.post(
                f"/v1/research-programs/cycles/{cycle['id']}/decision",
                json={
                    "expected_question_digest": cycle["question_digest"],
                    "decision": "approved",
                    "rationale": "Founder approved the bounded DISC-001 live pilot.",
                    "decided_by": "founder-operator",
                },
            )
            decided.raise_for_status()
            cycle = decided.json()
        events = client.get(f"/v1/research-programs/cycles/{cycle['id']}/events")
        events.raise_for_status()

    event_types = [item["event_type"] for item in events.json()]
    selection = cycle["digest"]["selection"]
    report = {
        "schema_version": "disc001-pilot-report-v1.0.0",
        "cycle_id": cycle["id"],
        "question": cycle["question"],
        "question_digest": cycle["question_digest"],
        "selection": selection,
        "event_types": event_types,
        "founder_decision": cycle["digest"].get("approval"),
        "execution_authority": False,
        "success": (
            "proposal_created" in event_types
            and (not args.approve or {"approved", "task_ready"}.issubset(event_types))
        ),
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
