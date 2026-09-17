#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from swarm_worker.executors.code_validation import (
    AsyncProcessRunner,
    CodeValidationExecutor,
    ExecutionPolicyError,
)
from swarm_worker.executors.engineering_mission import EngineeringMissionExecutor
from swarm_worker.models import Task
from swarm_worker.workflows import WorkflowLoader
from swarm_worker.workspace import TaskWorkspace, WorkspaceManager

REQUIRED_CAPABILITIES = {
    "alpha-strategy-engineering",
    "git",
    "python",
    "testing",
}
GENERIC_CODER_CAPABILITIES = {"git", "python", "testing"}
FULL_LOOP_STATES = [
    "mock_discovery_question_generated",
    "mock_predictive_and_falsifiable_gate_passed",
    "mock_data_availability_gate_passed",
    "mock_hypothesis_card_compiled",
    "mock_founder_mandate_approval_bound",
    "mock_leased_to_dedicated_engineer",
    "real_coding_agent_complete",
    "real_validation_complete",
    "real_structured_review_complete",
    "mock_independent_strategy_and_causality_reviews_passed",
    "mock_bounded_execution_approval_bound",
    "mock_eight_variant_backtest_complete",
    "mock_terminal_receipt_projected",
    "mock_bt009_publication_complete",
    "mock_next_hypothesis_replenished",
]


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def run(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def write_report(path: Path, report: dict) -> None:
    report["report_digest"] = canonical_digest(report)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    path.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))


def classify_engineering_failure(result: object, workspace: TaskWorkspace) -> dict:
    steps = getattr(result, "steps", [])
    failed = next((step for step in reversed(steps) if not step.success), None)
    detail = ""
    if failed is not None and failed.stderr_log:
        stderr = workspace.plan.attempt_directory / failed.stderr_log
        if stderr.is_file():
            detail = stderr.read_text(encoding="utf-8", errors="replace")[-4000:]
    lowered = detail.lower()
    review_path = workspace.plan.attempt_directory / "artifacts/review.json"
    review_rejected = False
    if review_path.is_file():
        try:
            review_rejected = json.loads(
                review_path.read_text(encoding="utf-8")
            ).get("approved") is False
        except (json.JSONDecodeError, OSError):
            review_rejected = False
    if "model is at capacity" in lowered:
        category = "provider_capacity"
        retryable = True
    elif (
        review_rejected
        or "approved" in lowered
        or getattr(failed, "name", "") == "independent-review"
    ):
        category = "independent_review_failed"
        retryable = False
    else:
        category = "engineering_step_failed"
        retryable = False
    return {
        "category": category,
        "retryable": retryable,
        "failed_step": getattr(failed, "name", None),
        "termination_reason": getattr(result, "termination_reason", None),
        "stderr_log": getattr(failed, "stderr_log", None),
    }


def classify_policy_exception(
    exc: ExecutionPolicyError, workspace: TaskWorkspace
) -> dict:
    coding_stderr = workspace.logs / "coding-agent.stderr.log"
    detail = (
        coding_stderr.read_text(encoding="utf-8", errors="replace")[-4000:]
        if coding_stderr.is_file()
        else ""
    )
    if "NETLINK_ROUTE" in detail and "Address family not supported" in detail:
        category = "sandbox_address_family_denied"
    elif "produced no changes" in str(exc):
        category = "engineering_no_changes"
    else:
        category = "engineering_policy_error"
    return {
        "category": category,
        "retryable": False,
        "failed_step": "coding-agent",
        "exception": type(exc).__name__,
        "detail": str(exc),
        "stderr_log": (
            "logs/coding-agent.stderr.log" if coding_stderr.is_file() else None
        ),
    }


def build_source(root: Path) -> tuple[Path, str]:
    repositories = root / "repositories"
    source = repositories / "alpha_loop_rehearsal"
    (source / "src/mock_alpha").mkdir(parents=True)
    (source / "tests").mkdir()
    (source / "research/hypotheses").mkdir(parents=True)
    (source / "src/mock_alpha/__init__.py").write_text("", encoding="utf-8")
    (source / "src/mock_alpha/strategy.py").write_text(
        "def signal(signed_return: float, quote_volume: float) -> int:\n"
        "    raise NotImplementedError('rehearsal strategy is not compiled')\n",
        encoding="utf-8",
    )
    (source / "research/hypotheses/mock-alpha.yaml").write_text(
        "status: awaiting_engineering\n",
        encoding="utf-8",
    )
    (source / "tests/test_strategy.py").write_text(
        "from pathlib import Path\n\n"
        "import yaml\n\n"
        "from mock_alpha.strategy import signal\n\n"
        "def test_extreme_positive_illiquid_move_fades():\n"
        "    assert signal(0.10, 100.0) == -1\n\n"
        "def test_extreme_negative_illiquid_move_fades():\n"
        "    assert signal(-0.10, 100.0) == 1\n\n"
        "def test_non_extreme_move_abstains():\n"
        "    assert signal(0.001, 100000.0) == 0\n\n"
        "def test_invalid_liquidity_abstains():\n"
        "    assert signal(0.10, 0.0) == 0\n\n"
        "def test_contract_declares_exactly_eight_variants():\n"
        "    contract = yaml.safe_load(\n"
        "        Path('research/hypotheses/mock-alpha.yaml').read_text()\n"
        "    )\n"
        "    assert contract['declared_variant_count'] == 8\n",
        encoding="utf-8",
    )
    (source / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\npythonpath = ['src']\n",
        encoding="utf-8",
    )
    (source / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.pytest_cache/\n",
        encoding="utf-8",
    )
    run(["git", "init", "-b", "main"], cwd=source)
    run(["git", "config", "user.name", "Alpha Loop Rehearsal"], cwd=source)
    run(["git", "config", "user.email", "rehearsal@invalid.local"], cwd=source)
    run(["git", "add", "."], cwd=source)
    run(["git", "commit", "-m", "fixture: initialize alpha loop rehearsal"], cwd=source)
    return repositories, run(["git", "rev-parse", "HEAD"], cwd=source)


def build_task(base_commit: str) -> Task:
    now = datetime.now(UTC)
    evidence = {
        "schema_version": "alpha-loop-rehearsal-evidence-v1.0.0",
        "question": (
            "Does an extreme point-in-time signed return magnitude per unit quote volume "
            "predict an opposite-direction next-bar return?"
        ),
        "dataset": "synthetic-no-market-data",
        "window_days": 365,
        "declared_variant_count": 8,
        "authority": {"capital": False, "orders": False, "promotion": False},
    }
    contract = {
        "repository": "alpha_loop_rehearsal",
        "workflow": "engineering-mission",
        "base_ref": base_commit,
        "milestone_id": "ALPHA-LOOP-REHEARSAL",
        "work_item_id": "mock-strategy-engineering",
        "objective": (
            "Implement the deterministic rehearsal strategy without changing tests. "
            "When abs(signed_return) / quote_volume is at least 0.001, return the "
            "opposite direction (-1 for positive, +1 for negative); otherwise return 0. "
            "Non-positive quote volume must return 0. Replace the "
            "hypothesis placeholder with a YAML contract containing the exact field "
            "`declared_variant_count: 8`, a 365-day window, next-bar timing, and no "
            "capital authority."
        ),
        "allowed_paths": [
            "src/mock_alpha/strategy.py",
            "research/hypotheses/mock-alpha.yaml",
        ],
        "context_paths": ["tests/test_strategy.py"],
        "evidence_context": json.dumps(evidence, sort_keys=True),
        "acceptance_criteria": [
            "All frozen tests pass without modification.",
            "The hypothesis declares 365 days and exactly eight variants.",
            "The strategy is deterministic and has no order or capital authority.",
        ],
        "stop_conditions": [
            "The requested behavior cannot be implemented within the two allowed files."
        ],
        "max_files_changed": 2,
        "max_diff_lines": 160,
        "max_duration_seconds": 900,
    }
    return Task(
        id=uuid4(),
        task_number="MOCK-ALPHA-G3",
        project="alpha_loop_rehearsal",
        task_type="engineering_mission",
        title="Engineer synthetic alpha strategy",
        objective=contract["objective"],
        status="running",
        priority=100,
        risk_level=1,
        assigned_agent_id=uuid4(),
        parent_task_id=None,
        created_by="alpha-loop-rehearsal",
        input_contract=contract,
        expected_outputs=["patch", "validation", "review", "pr_bundle"],
        acceptance_criteria=contract["acceptance_criteria"],
        approval_policy={"kind": "mock-explicit"},
        approval_required=True,
        plan_digest=canonical_digest(contract),
        required_capabilities=sorted(REQUIRED_CAPABILITIES),
        allowed_machines=["vm1-developer"],
        max_attempts=1,
        attempt_count=1,
        leased_at=now,
        lease_expires_at=now,
        last_execution_heartbeat_at=now,
        result={},
        failure={},
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=None,
    )


async def execute(
    task: Task,
    workspace: TaskWorkspace,
    *,
    codex_home: Path,
    model: str,
    workflow_directory: Path,
):
    workflow = WorkflowLoader(workflow_directory).load("engineering-mission")
    workflow = workflow.model_copy(
        update={"allowed_repositories": ["alpha_loop_rehearsal"]}
    )
    configured_virtualenv = os.environ.get("SWARM_ENGINEERING_VIRTUALENV")
    process_runner = AsyncProcessRunner(
        virtualenv=(Path(configured_virtualenv) if configured_virtualenv else None)
    )
    executor = EngineeringMissionExecutor(
        codex_home=codex_home,
        codex_model=model,
        timeout_seconds=900,
        heartbeat_interval_seconds=15,
        process_runner=process_runner,
        validation_executor=CodeValidationExecutor(
            heartbeat_interval_seconds=15,
            process_runner=process_runner,
        ),
    )

    async def heartbeat(_: dict[str, object]) -> None:
        return None

    return await executor.execute(
        task=task,
        workflow=workflow,
        workspace=workspace,
        heartbeat=heartbeat,
    )


def mock_terminal_receipt(task: Task, workspace: TaskWorkspace) -> dict:
    variants = [
        {"index": index, "net_r": round((index - 4) * 0.01, 4)}
        for index in range(8)
    ]
    classifications = {
        "positive": sum(item["net_r"] > 0 for item in variants),
        "negative": sum(item["net_r"] < 0 for item in variants),
        "invalid": sum(item["net_r"] == 0 for item in variants),
        "failed": 0,
    }
    receipt = {
        "schema_version": "alpha-loop-rehearsal-terminal-v1.0.0",
        "task_id": str(task.id),
        "plan_digest": task.plan_digest,
        "mode": "synthetic_no_market_data_no_capital",
        "window_days": 365,
        "declared_variant_count": 8,
        "variants": variants,
        "retained_classifications": classifications,
        "engineering_bundle": str(workspace.artifacts / "pr-bundle.json"),
        "capital_or_order_authority": False,
    }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def rehearse_full_loop_contract(
    task: Task, receipt: dict, *, generic_eligible: bool, dedicated_eligible: bool
) -> dict:
    checks = {
        "question_is_predictive": True,
        "question_is_falsifiable": True,
        "data_is_registered_and_point_in_time": True,
        "hypothesis_card_is_digest_bound": True,
        "weekly_mandate_covers_risk_zero_research": True,
        "generic_coder_is_ineligible": not generic_eligible,
        "dedicated_engineer_is_eligible": dedicated_eligible,
        "strategy_review_is_independent": True,
        "causality_review_is_independent": True,
        "execution_approval_is_digest_bound": True,
        "variant_budget_is_exactly_eight": receipt["declared_variant_count"] == 8,
        "research_window_is_one_year": receipt["window_days"] == 365,
        "all_terminal_classes_are_retained": set(
            receipt["retained_classifications"]
        )
        == {"positive", "negative", "invalid", "failed"},
        "publication_has_no_capital_authority": not receipt[
            "capital_or_order_authority"
        ],
        "campaign_replenishes_after_terminal_result": True,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise RuntimeError(f"Full-loop rehearsal failed closed: {', '.join(failed)}")
    return {
        "schema_version": "alpha-loop-mock-lifecycle-v1.0.0",
        "task_number": task.task_number,
        "checks": checks,
        "state_trace": FULL_LOOP_STATES,
        "production_api_calls": 0,
        "market_data_reads": 0,
        "orders_submitted": 0,
        "next_queue_depth": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--codex-home", type=Path, default=Path("/etc/invariance-swarm/codex-worker")
    )
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path("/home/omenka/.local/state/invariance-swarm/alpha-loop-rehearsal"),
    )
    args = parser.parse_args()

    run_id = uuid4()
    run_root = args.state_root / "runs" / str(run_id)
    run_root.mkdir(parents=True, mode=0o700)
    repositories, base_commit = build_source(run_root)
    task = build_task(base_commit)
    generic_eligible = REQUIRED_CAPABILITIES.issubset(GENERIC_CODER_CAPABILITIES)
    dedicated_eligible = REQUIRED_CAPABILITIES.issubset(REQUIRED_CAPABILITIES)
    if generic_eligible or not dedicated_eligible:
        raise RuntimeError("Exclusive lease routing rehearsal failed.")

    manager = WorkspaceManager(repositories, run_root / "workspaces")
    workspace = manager.prepare(
        task_id=task.id,
        task_number=task.task_number,
        attempt_number=1,
        repository="alpha_loop_rehearsal",
        base_ref=base_commit,
    )
    if not isinstance(workspace, TaskWorkspace):
        raise TypeError("Rehearsal workspace was not materialized.")
    try:
        result = asyncio.run(
            execute(
                task,
                workspace,
                codex_home=args.codex_home,
                model=args.model,
                workflow_directory=Path(__file__).resolve().parents[1] / "workflows",
            )
        )
    except ExecutionPolicyError as exc:
        report = {
            "schema_version": "alpha-loop-production-rehearsal-v1.0.0",
            "run_id": str(run_id),
            "success": False,
            "production_state_mutated": False,
            "market_data_used": False,
            "capital_or_order_authority": False,
            "failure": classify_policy_exception(exc, workspace),
            "lease_routing": {
                "required_capabilities": sorted(REQUIRED_CAPABILITIES),
                "generic_coder_eligible": generic_eligible,
                "dedicated_engineer_eligible": dedicated_eligible,
            },
            "workspace": str(workspace.plan.attempt_directory),
        }
        write_report(args.output, report)
        return 1
    if not result.success:
        report = {
            "schema_version": "alpha-loop-production-rehearsal-v1.0.0",
            "run_id": str(run_id),
            "success": False,
            "production_state_mutated": False,
            "market_data_used": False,
            "capital_or_order_authority": False,
            "failure": classify_engineering_failure(result, workspace),
            "lease_routing": {
                "required_capabilities": sorted(REQUIRED_CAPABILITIES),
                "generic_coder_eligible": generic_eligible,
                "dedicated_engineer_eligible": dedicated_eligible,
            },
            "engineering": result.model_dump(mode="json"),
            "workspace": str(workspace.plan.attempt_directory),
        }
        write_report(args.output, report)
        return 1

    receipt = mock_terminal_receipt(task, workspace)
    lifecycle = rehearse_full_loop_contract(
        task,
        receipt,
        generic_eligible=generic_eligible,
        dedicated_eligible=dedicated_eligible,
    )
    report = {
        "schema_version": "alpha-loop-production-rehearsal-v1.0.0",
        "run_id": str(run_id),
        "success": True,
        "production_state_mutated": False,
        "market_data_used": False,
        "capital_or_order_authority": False,
        "lease_routing": {
            "required_capabilities": sorted(REQUIRED_CAPABILITIES),
            "generic_coder_eligible": generic_eligible,
            "dedicated_engineer_eligible": dedicated_eligible,
        },
        "lifecycle": lifecycle,
        "state_trace": lifecycle["state_trace"],
        "engineering": result.model_dump(mode="json"),
        "terminal_receipt": receipt,
        "workspace": str(workspace.plan.attempt_directory),
    }
    write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
