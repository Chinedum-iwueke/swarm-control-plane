#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="/var/lib/invariance-swarm/gov004/report.json"
    )
    args = parser.parse_args()
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    headers = {"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"}
    with httpx.Client(base_url=base, headers=headers, timeout=120) as client:
        created = client.post(
            "/v1/governance-audit/exports",
            json={"requested_by": "founder-operator"},
        )
        created.raise_for_status()
        record = created.json()
        verified = client.post(
            "/v1/governance-audit/verify", json={"bundle": record["bundle"]}
        )
        verified.raise_for_status()
        replay = verified.json()
        retained = client.get(f"/v1/governance-audit/exports/{record['id']}")
        retained.raise_for_status()
        tampered = json.loads(json.dumps(record["bundle"]))
        tampered["events"][0]["actor"] = "tampered-actor"
        rejected = client.post("/v1/governance-audit/verify", json={"bundle": tampered})
        if rejected.status_code != 422:
            raise RuntimeError("Tampered export did not fail closed.")
        report = {
            "success": True,
            "export_id": record["id"],
            "schema_version": record["schema_version"],
            "event_count": record["event_count"],
            "bundle_digest": record["bundle_digest"],
            "key_id": record["key_id"],
            "signature_verified": replay["valid"],
            "reconstructed_projections": len(replay["reconstructed"]),
            "retained_export_matches": (
                retained.json()["bundle_digest"] == record["bundle_digest"]
            ),
            "tamper_rejected": True,
            "redaction_count": sum(
                len(item["redactions"]) for item in record["bundle"]["events"]
            ),
            "capital_or_order_authority": False,
        }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
