#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hypothesis-id", required=True)
    parser.add_argument("--dataset-manifest-digest", required=True)
    parser.add_argument("--representation-contract-digest", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/disc003/report.json"),
    )
    args = parser.parse_args()
    client = httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=60,
    )
    source = {
        "schema_version": "factor-experiment-language-v1.0.0",
        "representation_contract_digest": args.representation_contract_digest,
        "dataset_manifest_digest": args.dataset_manifest_digest,
        "decision_clock": "decision_close",
        "fields": {
            "close": {
                "unit": "usd",
                "domain": "positive",
                "clock": "decision_close",
                "availability_lag": 0,
            }
        },
        "parameters": {"lookback": [2, 4], "threshold": [0.0, 0.01]},
        "factors": {
            "lagged_return": {
                "expression": {
                    "op": "subtract",
                    "args": [
                        {
                            "op": "divide",
                            "args": [
                                {"op": "field", "args": ["close", 1]},
                                {"op": "field", "args": ["close", 2]},
                            ],
                        },
                        {"op": "constant", "args": [1]},
                    ],
                },
                "output_unit": "dimensionless",
                "missing_policy": "reject",
            }
        },
        "label": {"field": "close", "horizon": 1, "kind": "forward_return"},
        "maximum_trials": 4,
    }
    unsafe = json.loads(json.dumps(source))
    unsafe["factors"]["lagged_return"]["expression"] = {
        "op": "field",
        "args": ["close", 0],
    }
    rejected = client.post(
        "/v1/research/factor-programs",
        json={
            "program_key": "DISC003-UNSAFE-CURRENT-BAR",
            "hypothesis_id": args.hypothesis_id,
            "source": unsafe,
            "registered_by": "disc003-pilot",
        },
    )
    if rejected.status_code != 409:
        raise RuntimeError(f"Unsafe expression was accepted: {rejected.text}")
    response = client.post(
        "/v1/research/factor-programs",
        json={
            "program_key": "DISC003-LAGGED-MOMENTUM-R1",
            "hypothesis_id": args.hypothesis_id,
            "source": source,
            "registered_by": "disc003-pilot",
        },
    )
    if response.status_code == 409:
        existing = client.get(
            "/v1/research/factor-programs",
            params={"hypothesis_id": args.hypothesis_id},
        )
        existing.raise_for_status()
        record = next(
            item
            for item in existing.json()
            if item["program_key"] == "DISC003-LAGGED-MOMENTUM-R1"
        )
    else:
        response.raise_for_status()
        record = response.json()
    report = {
        "schema_version": "disc003-pilot-report-v1.0.0",
        "program_id": record["id"],
        "source_digest": record["source_digest"],
        "semantic_digest": record["semantic_digest"],
        "compiled_digest": record["compiled_digest"],
        "trial_count": record["compiled"]["trial_count"],
        "unsafe_current_bar_rejected": True,
        "action_authority": record["compiled"]["action_authority"],
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
