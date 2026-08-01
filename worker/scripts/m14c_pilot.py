from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the M14C storage note pilot")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--defer-days", type=int, default=30)
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    base_url = os.environ["SWARM_API_URL"].rstrip("/")
    document = {
        "note_key": "system-wide-storage-efficiency",
        "subject": "Audit system-wide storage efficiency",
        "finding": (
            "Bulletproof research memory was approximately 27.7 GB despite a "
            "limited set of known completed experiments; duplication, index, WAL, "
            "and retention costs require measurement before remediation."
        ),
        "evidence": [
            "docs/notes/system-wide-storage-efficiency.md",
            "bulletproof-memory-export:2ad6958b826fa803b872306f3873bdc1f0a9142487599a21accb1cadb54731af",
        ],
        "affected_systems": ["bulletproof_bt", "hermes-research-memory"],
        "urgency": "medium",
        "proposed_owner": "vm1-operational-memory-steward",
        "deferral_reason": None,
        "milestone_refs": ["M14C"],
        "repository_refs": ["bulletproof_bt", "swarm-control-plane"],
    }
    with httpx.Client(base_url=base_url, timeout=30) as client:
        recorded = client.post(
            "/v1/agent/operational-notes",
            headers={"Authorization": f"Bearer {state['token']}"},
            json=document,
        )
        recorded.raise_for_status()
        note = recorded.json()
        deferred_until = datetime.now(UTC) + timedelta(days=args.defer_days)
        transitioned = client.post(
            f"/v1/operational-notes/{note['id']}/transitions",
            headers={
                "Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"
            },
            json={
                "action": "defer",
                "actor": "founder-operator",
                "reason": (
                    "Defer destructive or space-reclaiming work until a bounded "
                    "measurement and restore-drill proposal is approved."
                ),
                "deferred_until": deferred_until.isoformat(),
                "evidence": ["docs/notes/system-wide-storage-efficiency.md"],
            },
        )
        if transitioned.status_code == 409 and note["status"] == "deferred":
            detail = client.get(
                f"/v1/operational-notes/{note['id']}",
                headers={
                    "Authorization": (
                        f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"
                    )
                },
            )
            detail.raise_for_status()
            result = detail.json()
        else:
            transitioned.raise_for_status()
            result = transitioned.json()
    print(
        json.dumps(
            {
                "note_id": result["id"],
                "record_digest": result["record_digest"],
                "status": result["status"],
                "deferred_until": result["deferred_until"],
                "event_sequence": [event["event_type"] for event in result["events"]],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
