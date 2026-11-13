#!/usr/bin/env python3
"""Queue a founder-authorized, planning-only source successor from retained evidence.

No campaign/mandate mutation, market-data scan, model call, or trade execution.
The parent admission and review remain immutable. Repeated invocation reuses the
exact task; changed inputs cannot consume an unchanged retry.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import httpx

from swarm_worker.policy import AlphaDataAdmissionContract


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-task-id", required=True)
    parser.add_argument("--review-task-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        parser.error("source commit must be an exact 40-character SHA")
    with httpx.Client(base_url=os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1"),
                     headers={"Authorization": "Bearer " + os.environ["SWARM_ORCHESTRATOR_TOKEN"]}, timeout=45) as client:
        def get_task(task_id):
            response = client.get(f"/v1/tasks/{task_id}")
            response.raise_for_status()
            return response.json()["task"]
        parent, review = get_task(args.parent_task_id), get_task(args.review_task_id)
        if parent["status"] != "succeeded" or parent["task_type"] != "alpha_data_admission":
            raise ValueError("Retained successful native admission is required")
        contract = deepcopy(parent["input_contract"])
        old_source = contract["source_commit"]
        subprocess.run(["git", "-C", str(args.repository), "merge-base", "--is-ancestor", old_source, args.source_commit], check=True)
        qualification = review["input_contract"]["qualification"]
        subject = review["input_contract"]["subject"]
        if subject.get("producer_task_id") != parent["id"] or subject.get("source_commit") != old_source:
            raise ValueError("Review is not bound to the retained admission and source")
        bundle = qualification["artifact_bundle"]
        evidence = {
            "discovery_candidate": qualification["card"],
            "representation_plan": bundle["representation_plan"],
            "validation_requirements": bundle["validation_requirements"],
            "dataset_bindings": bundle["dataset_bindings"], "window": bundle["window"],
        }
        contract.update(base_ref=args.source_commit, source_commit=args.source_commit, feasibility_evidence=evidence)
        AlphaDataAdmissionContract.model_validate(contract)
        number = "NPF-" + digest({"parent": parent["id"], "contract": contract})[:40]
        response = client.get("/v1/tasks", params={"project": parent["project"], "limit": 500, "compact": True})
        response.raise_for_status()
        task = next((item for item in response.json() if item["task_number"] == number), None)
        if task is not None:
            task = get_task(task["id"])
        if task is None:
            response = client.post("/v1/tasks", json={
                "task_number": number, "project": parent["project"], "task_type": "alpha_data_admission",
                "title": "Commission native requirements gate: planning-only source successor",
                "objective": args.reason,
                "parent_task_id": parent["id"], "created_by": "founder-operator",
                "risk_level": 0, "max_attempts": 1, "input_contract": contract,
                "required_capabilities": parent["required_capabilities"], "allowed_machines": parent["allowed_machines"],
                "expected_outputs": ["Digest-bound native feasibility receipt; no execution authority"],
                "acceptance_criteria": ["Retained inputs unchanged except authorized planner source", "Separate smoke/scientific feasibility", "No LLM review of infeasible inputs"],
            })
            response.raise_for_status()
            task = response.json()
        if task["input_contract"] != contract or task["parent_task_id"] != parent["id"]:
            raise ValueError("Commissioning task identity conflict")
        report = {
            "task_id": task["id"], "task_number": number, "status": task["status"],
            "parent_task_id": parent["id"], "parent_source_commit": old_source,
            "source_commit": args.source_commit, "input_digest": digest(evidence),
            "plan_digest": task["plan_digest"], "authorization_reason": args.reason,
            "capital_or_order_authority": False, "scientific_certification": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        args.output.chmod(0o600)
        print(json.dumps(report))


if __name__ == "__main__":
    main()
