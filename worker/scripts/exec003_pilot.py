#!/usr/bin/env python3
"""Register and replay an authoritative Bulletproof EXEC-003 receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "ascii"
        )
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    native = json.loads(args.native_report.read_text(encoding="utf-8"))
    receipt = native["receipt"]
    if not native.get("success") or receipt.get("milestone") != "EXEC-003":
        raise RuntimeError("native report is not a successful EXEC-003 producer report")
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    identity_payload = {
        "name": "explicit-cross-venue-identity",
        "version": "1.0.0",
        "producer": "bt.institutional.venue.venue_identity_receipt",
        "source_commit": receipt["source_commit"],
        "specification_digest": native["mapping_specification_digest"],
        "specification": native["mapping_specification"],
        "status": "active",
        "registered_by": "exec003-pilot",
    }
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        identity_response = client.post(
            "/v1/research/venue-identities", json=identity_payload
        )
        identity_response.raise_for_status()
        identity = identity_response.json()
        identity_replay = client.get(
            f"/v1/research/venue-identities/{identity['id']}"
        )
        identity_replay.raise_for_status()
        receipt_response = client.post(
            "/v1/research/quantitative-receipts",
            json={"receipt": receipt, "registered_by": "exec003-pilot"},
        )
        receipt_response.raise_for_status()
        registered = receipt_response.json()
        receipt_replay = client.get(
            f"/v1/research/quantitative-receipts/{registered['id']}"
        )
        receipt_replay.raise_for_status()

    success = (
        identity_replay.json()["specification_digest"]
        == native["mapping_specification_digest"]
        and receipt_replay.json()["receipt_digest"] == receipt["receipt_digest"]
        and receipt["result"]["qualified"] is True
        and not any(receipt["authority"].values())
    )
    result = {
        "schema_version": "exec003-cross-repository-pilot-v1.0.0",
        "success": success,
        "venue_identity_id": identity["id"],
        "venue_identity_digest": identity["specification_digest"],
        "quantitative_receipt_id": registered["id"],
        "receipt_digest": registered["receipt_digest"],
        "mapping_digest": receipt["result"]["mapping_digest"],
        "mapping_count": len(receipt["result"]["mappings"]),
        "comparison_route_count": len(receipt["result"]["routes"]),
        "capital_or_order_authority": False,
    }
    result["report_digest"] = digest(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output.chmod(0o600)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
