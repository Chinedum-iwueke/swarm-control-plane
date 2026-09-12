#!/usr/bin/env python3
"""Register and exactly replay authoritative Bulletproof EXEC-008 receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native = json.loads(args.native_report.read_text(encoding="utf-8"))
    receipts = native.get("producer_receipts", [])
    if (
        not native.get("success")
        or {item.get("milestone") for item in receipts} != {"EXEC-008"}
        or len(receipts) != 2
    ):
        raise RuntimeError(
            "native report is not a successful two-venue EXEC-008 report"
        )
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    schema_payload = {
        "name": "venue-adapter-certification-and-demo-parity",
        "version": "1.0.0",
        "producer": "bt.institutional.adapter_certification.adapter_certification_receipt",
        "source_commit": receipts[0]["source_commit"],
        "specification_digest": native["adapter_certification_specification_digest"],
        "specification": native["adapter_certification_specification"],
        "status": "active",
        "registered_by": "exec008-pilot",
    }
    registered_receipts = []
    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
        response = client.post(
            "/v1/research/adapter-certification-schemas", json=schema_payload
        )
        response.raise_for_status()
        schema = response.json()
        replay = client.get(
            f"/v1/research/adapter-certification-schemas/{schema['id']}"
        )
        replay.raise_for_status()
        for receipt in receipts:
            registered_response = client.post(
                "/v1/research/quantitative-receipts",
                json={"receipt": receipt, "registered_by": "exec008-pilot"},
            )
            registered_response.raise_for_status()
            registered = registered_response.json()
            receipt_replay = client.get(
                f"/v1/research/quantitative-receipts/{registered['id']}"
            )
            receipt_replay.raise_for_status()
            if receipt_replay.json()["receipt_digest"] != receipt["receipt_digest"]:
                raise RuntimeError("EXEC-008 receipt replay was not exact")
            registered_receipts.append(registered)
    results = [item["result"] for item in receipts]
    exact = (
        replay.json()["specification_digest"] == schema_payload["specification_digest"]
    )
    success = bool(
        exact
        and all(item["status"] == "conformance_only" for item in results)
        and all(item["qualified"] is False for item in results)
        and all(item["micro_live_eligible"] is False for item in results)
        and all(not any(item["authority"].values()) for item in receipts)
    )
    report = {
        "schema_version": "exec008-cross-repository-pilot-v1.0.0",
        "success": success,
        "adapter_certification_schema_id": schema["id"],
        "adapter_certification_schema_digest": schema["specification_digest"],
        "quantitative_receipts": [
            {
                "id": record["id"],
                "receipt_digest": record["receipt_digest"],
                "venue": result["venue"],
                "status": result["status"],
            }
            for record, result in zip(registered_receipts, results, strict=True)
        ],
        "venue_observed": False,
        "demo_execution_eligible": False,
        "micro_live_eligible": False,
        "capital_or_order_authority": False,
        "claim_boundary": (
            "Deterministic conformance is retained, but neither adapter is venue-demo "
            "certified until current venue-observed drills pass."
        ),
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
