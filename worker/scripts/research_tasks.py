#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field

from swarm_worker.policy import ResearchExperimentContract


class ResearchProgram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    project: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    program_id: str
    repository: str
    workflow: str
    base_ref: str
    hypothesis_id: str
    hypothesis: str
    dataset: str
    seed: int
    observations: int
    train_fraction: float
    transaction_cost_bps: float
    acceptance: dict

    def contract(self) -> ResearchExperimentContract:
        document = self.model_dump(exclude={"schema_version", "project"})
        return ResearchExperimentContract.model_validate(document)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "status"))
    parser.add_argument(
        "--program",
        type=Path,
        default=Path("research-programs/m8-pilot.yaml"),
    )
    parser.add_argument("--task-id")
    args = parser.parse_args()
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    if not api_url or not token:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    with httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        if args.action == "status":
            if not args.task_id:
                parser.error("status requires --task-id")
            response = client.get(f"/v1/tasks/{args.task_id}")
        else:
            program = _load_program(args.program)
            contract = program.contract()
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            response = client.post(
                "/v1/tasks",
                json={
                    "task_number": f"M8-RESEARCH-{timestamp}",
                    "project": program.project,
                    "task_type": "research_experiment",
                    "title": "M8 synthetic momentum research pilot",
                    "objective": (
                        "Execute and independently audit one predeclared "
                        "synthetic research hypothesis."
                    ),
                    "priority": 65,
                    "risk_level": 1,
                    "created_by": "founder-operator",
                    "input_contract": contract.model_dump(mode="json"),
                    "expected_outputs": [
                        "research-evidence.json",
                        "research-audit.json",
                        "research-report.md",
                    ],
                    "acceptance_criteria": [
                        "Dataset and source provenance are digest-bound.",
                        "Out-of-sample and cost-stress metrics are reported.",
                        "The selection-bias audit records one hypothesis.",
                        "The finding cannot promote itself to live trading.",
                    ],
                    "approval_policy": {"kind": "automatic", "risk": 1},
                    "approval_required": False,
                    "required_capabilities": [
                        "git",
                        "python",
                        "backtesting",
                        "research-audit",
                    ],
                    "allowed_machines": ["vm1-developer"],
                    "max_attempts": 1,
                },
            )
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


def _load_program(path: Path) -> ResearchProgram:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ResearchProgram.model_validate(document)


if __name__ == "__main__":
    raise SystemExit(main())
