import asyncio
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from swarm_worker.executors.alpha_strategy_review import (
    AlphaStrategyReviewContract,
    AlphaStrategyReviewExecutor,
    StrategyReviewVerdict,
    review_digest,
)


def contract():
    qualification = {"card": {"claim": "exact card"}, "artifact_bundle": {"strategy_spec": "pinned"}}
    subject = {
        "source_commit": "a" * 40, "producer_agent_ids": ["10000000-0000-4000-8000-000000000001"],
        "card_digest": review_digest(qualification["card"]),
        "artifact_bundle_digest": review_digest(qualification["artifact_bundle"]),
    }
    return {
        "repository": "bulletproof_bt", "workflow": "alpha-strategy-review", "base_ref": "a" * 40,
        "route_id": "20000000-0000-4000-8000-000000000001",
        "assignment_id": "30000000-0000-4000-8000-000000000001",
        "evaluator_agent_id": "40000000-0000-4000-8000-000000000001",
        "review_kind": "strategy_spec", "subject_digest": review_digest(subject),
        "subject": subject, "qualification": qualification, "authority": "review_only_no_execution",
    }


@pytest.mark.parametrize("change", ["subject", "card", "artifacts", "source", "self", "authority"])
def test_review_contract_rejects_substitution_and_self_review(change):
    payload = contract()
    if change == "subject":
        payload["subject_digest"] = "f" * 64
    elif change == "card":
        payload["qualification"]["card"]["claim"] = "substitute"
    elif change == "artifacts":
        payload["qualification"]["artifact_bundle"] = {}
    elif change == "source":
        payload["base_ref"] = "b" * 40
    elif change == "self":
        payload["evaluator_agent_id"] = payload["subject"]["producer_agent_ids"][0]
    else:
        payload["authority"] = "execute"
    with pytest.raises(ValidationError):
        AlphaStrategyReviewContract.model_validate(payload)


def test_review_cannot_approve_unresolved_findings():
    with pytest.raises(ValidationError, match="unresolved blockers"):
        StrategyReviewVerdict(subject_digest="a" * 64, verdict="approve", checks=["causal timing"],
                              rationale="The causal timing remains unverifiable.", blockers=["future join"])


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", ["approve", "reject"])
async def test_read_only_reviewer_retains_real_verdict_without_execution_authority(tmp_path, verdict):
    payload = contract()
    for name in ("artifacts", "logs", "repository"):
        (tmp_path / name).mkdir()
    workspace = SimpleNamespace(
        artifacts=tmp_path / "artifacts", logs=tmp_path / "logs", repository=tmp_path / "repository",
        plan=SimpleNamespace(resolved_base_commit=payload["base_ref"]),
    )
    process = SimpleNamespace(returncode=0)

    class Runner:
        async def start(self, args, **kwargs):
            assert args[args.index("--sandbox") + 1] == "read-only"
            assert "--ephemeral" in args
            assert "review_only_no_execution" in kwargs["stdin"].read().decode()
            output = {
                "subject_digest": payload["subject_digest"], "verdict": verdict,
                "rationale": "Reviewed the exact frozen card and pinned source.",
                "checks": ["semantic fidelity"], "blockers": [] if verdict == "approve" else ["missing timing"],
            }
            (workspace.artifacts / "strategy-review.json").write_text(json.dumps(output))
            return SimpleNamespace(process=process)

    executor = AlphaStrategyReviewExecutor(codex_home=tmp_path, codex_model="test-model",
                                           heartbeat_interval_seconds=1, process_runner=Runner(), effective_uid=lambda: 1000)
    task = SimpleNamespace(input_contract=payload, assigned_agent_id=UUID(payload["evaluator_agent_id"]), attempt_count=1)
    result = await executor.execute(task=task, workflow=SimpleNamespace(name=payload["workflow"], steps=[], timeout_seconds=60),
                                    workspace=workspace, heartbeat=None)
    assert result.success
    assert result.summary["alpha_strategy_review"]["verdict"] == verdict
    assert result.summary["review_digest"] == review_digest(result.summary["alpha_strategy_review"])
    assert "authority" not in result.summary


@pytest.mark.asyncio
async def test_lease_loss_terminates_the_owned_reviewer_process(tmp_path):
    payload = contract()
    for name in ("artifacts", "logs", "repository"):
        (tmp_path / name).mkdir()
    workspace = SimpleNamespace(
        artifacts=tmp_path / "artifacts", logs=tmp_path / "logs", repository=tmp_path / "repository",
        plan=SimpleNamespace(resolved_base_commit=payload["base_ref"]),
    )

    class Process:
        returncode = None

        async def wait(self):
            await asyncio.sleep(10)

    class Runner:
        terminated = False

        async def start(self, *args, **kwargs):
            return SimpleNamespace(process=Process())

        async def terminate(self, running, *, grace_seconds):
            self.terminated = True
            running.process.returncode = -15

    runner = Runner()
    executor = AlphaStrategyReviewExecutor(codex_home=tmp_path, codex_model="test-model",
                                           heartbeat_interval_seconds=1, process_runner=runner, effective_uid=lambda: 1000)

    async def lost(metadata):
        raise RuntimeError("lease lost")

    task = SimpleNamespace(input_contract=payload, assigned_agent_id=UUID(payload["evaluator_agent_id"]), attempt_count=1)
    with pytest.raises(RuntimeError, match="lease lost"):
        await executor.execute(task=task, workflow=SimpleNamespace(name=payload["workflow"], steps=[], timeout_seconds=60),
                               workspace=workspace, heartbeat=lost)
    assert runner.terminated
