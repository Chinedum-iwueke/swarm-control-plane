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
    parser.add_argument("--factor-program-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/disc004/report.json"),
    )
    args = parser.parse_args()
    client = httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=60,
    )
    created = client.post(
        "/v1/research/statistical-searches",
        json={
            "campaign_key": "DISC004-BAYESIAN-PILOT-R1",
            "factor_program_id": args.factor_program_id,
            "method": "bayesian",
            "seed": 20260827,
            "objective": {"metric": "synthetic_sharpe", "direction": "maximize"},
            "budget": {
                "maximum_evaluations": 3,
                "maximum_batches": 3,
                "batch_size": 1,
            },
            "exploration_weight": 0.5,
            "registered_by": "disc004-pilot",
        },
    )
    if created.status_code == 409:
        listing = client.get("/v1/research/statistical-searches")
        listing.raise_for_status()
        campaign = next(
            item
            for item in listing.json()
            if item["campaign_key"] == "DISC004-BAYESIAN-PILOT-R1"
        )
    else:
        created.raise_for_status()
        campaign = created.json()
    outcomes = [
        ("completed", 0.25),
        ("failed", None),
        ("completed", 0.75),
    ]
    while campaign["status"] == "active":
        index = campaign["observed_count"]
        proposal = client.post(
            f"/v1/research/statistical-searches/{campaign['id']}/proposals"
        )
        proposal.raise_for_status()
        trial_digest = proposal.json()["proposals"][0]["trial_digest"]
        status, value = outcomes[index]
        observation = {
            "trial_digest": trial_digest,
            "status": status,
            "objective_value": value,
            "result_digest": digest(
                {"trial_digest": trial_digest, "status": status, "value": value}
            ),
        }
        recorded = client.post(
            f"/v1/research/statistical-searches/{campaign['id']}/observations",
            json={"observations": [observation]},
        )
        recorded.raise_for_status()
        campaign = recorded.json()
    replay = client.get(f"/v1/research/statistical-searches/{campaign['id']}/events")
    replay.raise_for_status()
    chain = replay.json()
    statuses = [
        item["status"]
        for event in chain["events"]
        if event["event_type"] == "observed"
        for item in event["detail"]["observations"]
    ]
    report = {
        "schema_version": "disc004-pilot-report-v1.0.0",
        "campaign_id": campaign["id"],
        "specification_digest": campaign["specification_digest"],
        "status": campaign["status"],
        "proposed_count": campaign["proposed_count"],
        "observed_count": campaign["observed_count"],
        "observation_statuses": statuses,
        "event_chain_valid": chain["valid"],
        "event_head_digest": chain["head_digest"],
        "action_authority": False,
    }
    if campaign["status"] != "complete" or statuses != [
        "completed",
        "failed",
        "completed",
    ]:
        raise RuntimeError("Fixed-budget campaign did not retain the complete history.")
    if not chain["valid"]:
        raise RuntimeError("Campaign event chain is invalid.")
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
