#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def payload(key, expression, index, generator_index=None):
    generator = {
        "provider": "openai",
        "model": "codex",
        "version": "2026-08",
        "seed": 20260827,
        "candidate_index": index if generator_index is None else generator_index,
    }
    proposal = {
        "expression": expression,
        "output_unit": "dimensionless",
        "generator": generator,
    }
    return {
        "candidate_key": key,
        **proposal,
        "output_digest": digest(proposal),
        "submitted_by": "disc005-pilot",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-program-id", required=True)
    parser.add_argument("--prompt-policy-bundle-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/disc005/report.json"),
    )
    args = parser.parse_args()
    client = httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=60,
    )
    created = client.post(
        "/v1/research/symbolic-searches",
        json={
            "run_key": "DISC005-SYMBOLIC-PILOT-R1",
            "base_factor_program_id": args.factor_program_id,
            "prompt_policy_bundle_id": args.prompt_policy_bundle_id,
            "constraints": {
                "maximum_candidates": 4,
                "maximum_nodes": 12,
                "maximum_depth": 6,
                "maximum_constants": 1,
                "allowed_operators": ["field", "constant", "add", "multiply", "divide"],
                "required_fields": ["close"],
                "allow_parameters": False,
            },
            "generated_by": "disc005-pilot",
        },
    )
    if created.status_code == 409:
        listing = client.get("/v1/research/symbolic-searches")
        listing.raise_for_status()
        run = next(
            item
            for item in listing.json()
            if item["run_key"] == "DISC005-SYMBOLIC-PILOT-R1"
        )
    else:
        created.raise_for_status()
        run = created.json()
    ratio = {
        "op": "divide",
        "args": [
            {"op": "field", "args": ["close", 1]},
            {"op": "field", "args": ["close", 2]},
        ],
    }
    valid = {"op": "add", "args": [ratio, {"op": "constant", "args": [0.01]}]}
    duplicate = {"op": "add", "args": [{"op": "constant", "args": [0.01]}, ratio]}
    hostile = {"op": "python_eval", "args": ["__import__('os').system('id')"]}
    changed_same_generation = {
        "op": "multiply",
        "args": [ratio, {"op": "constant", "args": [2]}],
    }
    candidates = [
        payload("DISC005-CANDIDATE-1", valid, 0),
        payload("DISC005-CANDIDATE-2", duplicate, 1),
        payload("DISC005-CANDIDATE-3", hostile, 2),
        payload("DISC005-CANDIDATE-4", changed_same_generation, 3, generator_index=0),
    ]
    for item in candidates[run["candidate_count"] :]:
        response = client.post(
            f"/v1/research/symbolic-searches/{run['id']}/candidates", json=item
        )
        response.raise_for_status()
    current = client.get(f"/v1/research/symbolic-searches/{run['id']}")
    current.raise_for_status()
    run = current.json()
    listing = client.get(f"/v1/research/symbolic-searches/{run['id']}/candidates")
    listing.raise_for_status()
    retained = listing.json()
    statuses = [item["status"] for item in retained]
    violations = sorted(
        {violation for item in retained for violation in item["violations"]}
    )
    if run["status"] != "complete" or statuses != [
        "accepted",
        "duplicate",
        "rejected",
        "rejected",
    ]:
        raise RuntimeError(f"Unexpected symbolic-search outcome: {run} {statuses}")
    report = {
        "schema_version": "disc005-pilot-report-v1.0.0",
        "run_id": run["id"],
        "constraints_digest": run["constraints_digest"],
        "status": run["status"],
        "candidate_statuses": statuses,
        "violations": violations,
        "accepted_count": run["accepted_count"],
        "all_lineage_retained": len(retained) == 4,
        "generated_code_executed": False,
        "action_authority": False,
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
