#!/usr/bin/env python3
"""Exercise UI-004 without granting execution authority."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def _client() -> httpx.Client:
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not token:
        raise RuntimeError("SWARM_ORCHESTRATOR_TOKEN is required.")
    return httpx.Client(
        base_url=os.environ.get("SWARM_API_URL", "http://100.112.117.59:8787").rstrip(
            "/"
        ),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def _request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def main() -> int:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    with _client() as client:
        task = _request(
            client,
            "POST",
            "/v1/tasks",
            json={
                "task_number": f"UI004-REPLAY-{timestamp}",
                "project": "swarm-control-plane",
                "task_type": "approval_contract_validation",
                "title": "UI-004 digest-safe approval replay",
                "objective": "Prove stale reviews fail closed and retain a current rejection receipt.",
                "priority": 10,
                "risk_level": 0,
                "created_by": "ui004-pilot",
                "input_contract": {
                    "workflow": "approval-contract-validation",
                    "execution_authority": False,
                },
                "expected_outputs": ["digest-bound rejection receipt"],
                "acceptance_criteria": [
                    "A stale review digest is rejected.",
                    "The exact current review digest is retained in the decision receipt.",
                ],
                "approval_policy": {"kind": "founder", "pilot": True},
                "approval_required": True,
                "required_capabilities": [],
                "allowed_machines": [],
                "max_attempts": 1,
            },
        )
        center = _request(client, "GET", "/v1/approval-center")
        review = next(
            item
            for item in center["items"]
            if item["approval"]["task_id"] == task["id"]
        )
        stale = client.post(
            f"/v1/approval-center/{review['approval']['id']}/reject",
            json={
                "actor": "founder-operator",
                "reason": "UI-004 stale digest rejection rehearsal.",
                "expected_review_digest": "0" * 64,
            },
        )
        if stale.status_code != 409:
            raise RuntimeError(
                f"Stale review did not fail closed: HTTP {stale.status_code}"
            )
        receipt = _request(
            client,
            "POST",
            f"/v1/approval-center/{review['approval']['id']}/reject",
            json={
                "actor": "founder-operator",
                "reason": "Reject the no-execution UI-004 validation fixture after exact review.",
                "expected_review_digest": review["review_digest"],
            },
        )
        retained = _request(
            client,
            "GET",
            f"/v1/approval-center/{review['approval']['id']}",
        )

    event = next(
        item
        for item in retained["events"]
        if item["event_type"] == "approval_center_decision_receipt"
    )
    report = {
        "schema_version": "ui004-pilot-report-v1.0.0",
        "task_id": task["id"],
        "approval_id": review["approval"]["id"],
        "execution_authority": False,
        "stale_review_rejected": True,
        "decision": receipt["action"],
        "decision_status": receipt["approval"]["status"],
        "review_digest": receipt["review_digest"],
        "receipt_digest": receipt["receipt_digest"],
        "receipt_event_id": event["id"],
        "success": receipt["approval"]["status"] == "rejected",
    }
    report["report_digest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path(
        os.environ.get("UI004_REPORT", "/var/lib/invariance-swarm/ui004/report.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
