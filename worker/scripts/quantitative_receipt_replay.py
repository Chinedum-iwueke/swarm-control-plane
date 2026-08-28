#!/usr/bin/env python3
"""Register and exactly replay Bulletproof quantitative producer receipts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.report.read_text(encoding="utf-8"))
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    registered = []
    with httpx.Client(
        base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=60
    ) as client:
        for receipt in document["receipts"]:
            response = client.post(
                "/v1/research/quantitative-receipts",
                json={
                    "receipt": receipt,
                    "registered_by": "quantitative-receipt-bridge",
                },
            )
            response.raise_for_status()
            record = response.json()
            replay = client.get(f"/v1/research/quantitative-receipts/{record['id']}")
            replay.raise_for_status()
            if replay.json()["receipt_digest"] != receipt["receipt_digest"]:
                raise RuntimeError("quantitative receipt replay drift")
            registered.append(
                {
                    "milestone": receipt["milestone"],
                    "id": record["id"],
                    "receipt_digest": receipt["receipt_digest"],
                }
            )
    result = {
        "schema_version": "quantitative-cross-repository-replay-v1.0.0",
        "success": len(registered) == 15,
        "capital_or_order_authority": False,
        "registered": registered,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
