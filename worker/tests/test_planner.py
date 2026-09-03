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
from swarm_worker.planner.engine import CodexProposalPlanner, PlannerError
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


def test_clarification_requires_exact_field_and_format_guidance() -> None:
    payload = valid_proposal()
    payload.update(
        {
            "recommended_action": "needs_clarification",
            "proposed_task": None,
            "clarification_questions": ["Which dataset should be used?"],
            "unresolved_fields": ["dataset"],
            "specification_format": {},
        }
    )

    with pytest.raises(ValidationError, match="accepted format guidance"):
        FounderProposalDocument.model_validate(payload)

    payload["specification_format"] = {
        "dataset": "Canonical dataset ID, for example synthetic-regime-v1"
    }
    assert FounderProposalDocument.model_validate(payload).unresolved_fields == [
        "dataset"
    ]


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
    schema = CodexProposalPlanner._codex_output_schema()

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if value.get("type") == "object":
                assert isinstance(properties, dict)
                assert value["additionalProperties"] is False
                assert value["required"] == list(properties)
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)

    inspect(schema)
    specification_format = schema["properties"]["specification_format"]
    assert specification_format["type"] == "array"
    assert specification_format["items"]["required"] == ["field", "format"]


def test_planner_normalizes_strict_format_rows_to_public_mapping() -> None:
    payload = valid_proposal()
    payload["specification_format"] = [
        {
            "field": "dataset",
            "format": "Canonical dataset ID, for example synthetic-regime-v1",
        }
    ]

    normalized = CodexProposalPlanner._normalize_output(payload)

    assert normalized["specification_format"] == {
        "dataset": "Canonical dataset ID, for example synthetic-regime-v1"
    }
    assert FounderProposalDocument.model_validate(normalized).recommended_action == (
        "create_task"
    )


def test_planner_rejects_duplicate_strict_format_rows() -> None:
    payload = valid_proposal()
    payload["specification_format"] = [
        {"field": "dataset", "format": "Canonical dataset ID"},
        {"field": "dataset", "format": "Another format"},
    ]

    with pytest.raises(PlannerError, match="duplicated"):
        CodexProposalPlanner._normalize_output(payload)


def test_planner_accepts_direct_conversational_response_without_task() -> None:
    payload = valid_proposal()
    payload.update(
        {
            "summary": "The current catalog supports a bounded synthetic test.",
            "interpretation": "This answers the founder without scheduling work.",
            "recommended_action": "respond",
            "target_role": None,
            "target_role_reason": None,
            "safety_constraints": [],
            "proposed_task": None,
        }
    )

    document = FounderProposalDocument.model_validate(payload)

    assert document.recommended_action == "respond"
    assert document.proposed_task is None


def test_conversation_prompt_preserves_turns_and_governed_defaults() -> None:
    context = [
        "Backtest whether an equity risk-off regime predicts BTC residual returns.",
        "January to February 2022; use a stable universe.",
        "Use reasonable defaults and do not ask me to invent identifiers.",
    ]
    task = Task.model_construct(
        task_type="founder_request",
        project="bulletproof_bt",
        title="BTC residual research",
        risk_level=1,
        acceptance_criteria=[],
        input_contract={
            "schema_version": 2,
            "request_kind": "task",
            "objective": context[0],
            "conversation_id": "conversation-id",
            "conversation_revision": 3,
            "conversation_context": context,
            "suggested_identifiers": {
                "program_id": "HERMES-THREAD",
                "hypothesis_id": "HERMES-THREAD-H1",
            },
            "specification_guide": {
                "reasonable_defaults": {"base_ref": "main"},
                "formats": {"train_fraction": "decimal 0.50-0.80"},
            },
        },
    )

    prompt = CodexProposalPlanner._prompt(task)

    assert all(turn in prompt for turn in context)
    assert "HERMES-THREAD-H1" in prompt
    assert "do not ask the founder to invent program_id" in prompt
    assert "exact field name" in prompt
    assert "Never call a choice best without evidence" in prompt
    assert "founder may reply with only the option number" in prompt
    assert "single clarification_questions entry" in prompt
    assert "Do not claim that a domain specialist was consulted" in prompt
    assert "Never ask again for a value the founder already supplied" in prompt


def test_conversation_prompt_receives_bounded_grounding_context() -> None:
    task = Task.model_construct(
        task_type="founder_request",
        project="bulletproof_bt",
        title="Explain available research data",
        risk_level=0,
        acceptance_criteria=[],
        input_contract={
            "schema_version": 2,
            "request_kind": "task",
            "objective": "What data can the research agents use?",
            "conversation_id": "conversation-id",
            "conversation_revision": 1,
            "conversation_context": ["What data can the research agents use?"],
            "suggested_identifiers": {},
            "specification_guide": {},
            "grounding_context": {
                "datasets": [{"key": "binance-btcusdt-1h", "digest": "d" * 64}],
                "task_capabilities": [{"slug": "research-runner"}],
                "claim_boundary": "advisory evidence only",
            },
        },
    )

    prompt = CodexProposalPlanner._prompt(task)

    assert "binance-btcusdt-1h" in prompt
    assert "research-runner" in prompt
    assert "advisory evidence only" in prompt


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
        payload = valid_proposal()
        payload["specification_format"] = []
        output_path.write_text(json.dumps(payload), encoding="utf-8")
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
async def test_grounded_question_stops_after_reasoning_without_compilation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invocations = 0
    credential_home = tmp_path / "credentials"
    credential_home.mkdir()

    class Process:
        returncode = 0

        async def communicate(self, _: bytes):
            return b"", b""

    async def create_subprocess_exec(*args: str, **_: object):
        nonlocal invocations
        invocations += 1
        output_path = Path(args[args.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "response_kind": "respond",
                    "summary": "The catalog contains one immutable BTC dataset.",
                    "interpretation": "The founder asked a question, not for execution.",
                    "grounding_citations": ["dataset-digest:" + "d" * 64],
                    "clarification_questions": [],
                    "unresolved_fields": [],
                    "specification_format": [],
                }
            ),
            encoding="utf-8",
        )
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
        project="bulletproof_bt",
        title="Describe available data",
        risk_level=0,
        acceptance_criteria=[],
        input_contract={
            "schema_version": 2,
            "request_kind": "task",
            "objective": "What BTC data is available?",
            "conversation_id": "conversation-id",
            "conversation_revision": 1,
            "conversation_context": ["What BTC data is available?"],
            "suggested_identifiers": {},
            "specification_guide": {},
            "grounding_context": {"datasets": [{"digest": "d" * 64}]},
        },
    )

    response = await planner.plan(task)

    assert invocations == 1
    assert response.recommended_action == "respond"
    assert response.proposed_task is None
    assert "dataset-digest" in response.summary


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
