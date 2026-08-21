from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from swarm_worker.models import FounderProposalDocument, Task
from swarm_worker.planner.config import PlannerSettings
from swarm_worker.planner.engine import CodexProposalPlanner
from swarm_worker.planner.service import FounderIntakePlannerService


def valid_proposal() -> dict:
    return {
        "schema_version": 1,
        "summary": "Create a bounded validation task.",
        "interpretation": "The request maps to the named validation workflow.",
        "recommended_action": "create_task",
        "assumptions": [],
        "clarification_questions": [],
        "target_role": "Restricted engineering worker",
        "target_role_reason": "It owns validation.",
        "safety_constraints": ["Do not write to the primary checkout."],
        "proposed_task": {
            "project": "swarm-control-plane",
            "task_type": "code_validation",
            "title": "Validate the control plane",
            "objective": "Compile and test the isolated repository worktree.",
            "input_contract": {
                "repository": "swarm-control-plane",
                "workflow": "code-validation",
                "base_ref": "main",
            },
            "approval_policy": {"kind": "automatic", "risk": 0},
            "required_capabilities": ["git", "python", "testing"],
            "allowed_machines": ["vm1-developer"],
        },
    }


def test_planner_proposal_rejects_commands_and_unknown_fields() -> None:
    payload = valid_proposal()
    payload["proposed_task"]["input_contract"]["shell"] = "pytest"
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(payload)


def test_planner_proposal_rejects_invented_worker_route() -> None:
    payload = valid_proposal()
    payload["proposed_task"]["allowed_machines"] = ["server-local"]
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(payload)


def test_planner_child_environment_excludes_worker_token(tmp_path) -> None:
    os.environ["SWARM_AGENT_TOKEN"] = "agent-token-must-not-propagate"
    planner = CodexProposalPlanner(
        codex_binary=tmp_path / "codex",
        codex_home=tmp_path / "home",
        model="test-model",
        timeout_seconds=1,
        working_directory=tmp_path,
    )
    environment = planner._environment()
    assert "SWARM_AGENT_TOKEN" not in environment
    assert "agent-token-must-not-propagate" not in str(environment)


def test_planner_output_schema_is_closed_and_requires_declared_fields() -> None:
    schema = CodexProposalPlanner._strict_output_schema(
        FounderProposalDocument.model_json_schema()
    )

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                assert value["additionalProperties"] is False
                assert value["required"] == list(properties)
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)

    inspect(schema)


@pytest.mark.asyncio
async def test_planner_allows_its_ephemeral_non_git_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command: tuple[str, ...] = ()
    credential_home = tmp_path / "credentials"
    credential_home.mkdir()

    class Process:
        returncode = 0

        async def communicate(self, _: bytes):
            return b"", b""

    async def create_subprocess_exec(*args: str, **_: object):
        nonlocal command
        command = args
        output_path = Path(args[args.index("--output-last-message") + 1])
        output_path.write_text(json.dumps(valid_proposal()), encoding="utf-8")
        return Process()

    monkeypatch.setattr(
        "swarm_worker.planner.engine.asyncio.create_subprocess_exec",
        create_subprocess_exec,
    )
    planner = CodexProposalPlanner(
        codex_binary=tmp_path / "codex",
        codex_home=credential_home,
        model="test-model",
        timeout_seconds=1,
        working_directory=tmp_path,
    )
    task = Task.model_construct(
        task_type="founder_request",
        project="swarm-control-plane",
        title="Plan a bounded validation",
        risk_level=0,
        acceptance_criteria=[],
        input_contract={
            "schema_version": 1,
            "request_kind": "task",
            "objective": "Create a bounded validation task.",
        },
    )

    proposal = await planner.plan(task)

    assert proposal.recommended_action == "create_task"
    assert "--skip-git-repo-check" in command


@pytest.mark.asyncio
async def test_planner_lifecycle_submits_before_completion(tmp_path: Path) -> None:
    events: list[str] = []
    proposal = FounderProposalDocument.model_validate(valid_proposal())
    task = Task.model_construct(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        task_type="founder_request",
        input_contract={
            "schema_version": 1,
            "request_kind": "task",
            "objective": "Create a bounded validation task.",
        },
    )

    class API:
        async def get_identity(self):
            events.append("identity")
            return SimpleNamespace(
                slug="vm1-founder-intake-planner",
                machine="vm1-developer",
                is_enabled=True,
                capabilities=["founder-intake"],
            )

        async def send_agent_heartbeat(self, _):
            events.append("agent_heartbeat")

        async def lease_task(self, _):
            events.append("lease")
            return SimpleNamespace(task=task, lease_token="lease-token")

        async def start_task(self, *_):
            events.append("start")

        async def submit_founder_proposal(self, *_):
            events.append("submit_proposal")
            return SimpleNamespace(
                id=UUID("33333333-3333-4333-8333-333333333333"),
                proposal_digest="a" * 64,
            )

        async def complete_task(self, *_):
            events.append("complete")

    class Planner:
        async def plan(self, _):
            events.append("plan")
            return proposal

    settings = PlannerSettings(
        swarm_api_url="http://control-plane.test",
        swarm_agent_token="agent-token-that-is-long-enough",
        swarm_planner_workspace=tmp_path,
        swarm_role_package_manifest=(
            Path(__file__).parents[1]
            / "role-packages/founder-intake-planner/manifest.yaml"
        ),
        swarm_workflow_directory=Path(__file__).parents[1] / "workflows",
    )
    result = await FounderIntakePlannerService(
        settings,
        api=API(),  # type: ignore[arg-type]
        planner=Planner(),  # type: ignore[arg-type]
    ).run_once()

    assert result.kind == "succeeded"
    assert events == [
        "identity",
        "agent_heartbeat",
        "lease",
        "start",
        "plan",
        "submit_proposal",
        "complete",
    ]
