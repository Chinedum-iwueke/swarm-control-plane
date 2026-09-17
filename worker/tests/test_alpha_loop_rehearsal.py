import importlib.util
import json
from pathlib import Path

import pytest

from swarm_worker.role_package import load_role_package

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "alpha_loop_rehearsal", ROOT / "scripts/alpha_loop_rehearsal.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rehearsal_contract_excludes_generic_coder_and_has_no_authority():
    task = MODULE.build_task("a" * 40)
    assert not MODULE.REQUIRED_CAPABILITIES.issubset(
        MODULE.GENERIC_CODER_CAPABILITIES
    )
    assert task.required_capabilities == sorted(MODULE.REQUIRED_CAPABILITIES)
    assert task.task_number == "MOCK-ALPHA-G3"
    assert task.risk_level == 1
    evidence = json.loads(task.input_contract["evidence_context"])
    assert evidence["authority"] == {
        "capital": False,
        "orders": False,
        "promotion": False,
    }


def test_rehearsal_terminal_receipt_is_bounded_and_retains_all_outcomes(tmp_path):
    task = MODULE.build_task("a" * 40)
    workspace = type(
        "Workspace",
        (),
        {"artifacts": tmp_path / "artifacts"},
    )()
    receipt = MODULE.mock_terminal_receipt(task, workspace)
    assert receipt["declared_variant_count"] == 8
    assert receipt["window_days"] == 365
    assert len(receipt["variants"]) == 8
    assert receipt["retained_classifications"] == {
        "positive": 3,
        "negative": 4,
        "invalid": 1,
        "failed": 0,
    }
    assert receipt["capital_or_order_authority"] is False
    assert len(receipt["receipt_digest"]) == 64


def test_full_loop_rehearsal_covers_terminal_publication_and_replenishment(tmp_path):
    task = MODULE.build_task("a" * 40)
    workspace = type("Workspace", (), {"artifacts": tmp_path / "artifacts"})()
    receipt = MODULE.mock_terminal_receipt(task, workspace)

    lifecycle = MODULE.rehearse_full_loop_contract(
        task,
        receipt,
        generic_eligible=False,
        dedicated_eligible=True,
    )

    assert lifecycle["production_api_calls"] == 0
    assert lifecycle["orders_submitted"] == 0
    assert lifecycle["next_queue_depth"] == 1
    assert lifecycle["state_trace"] == MODULE.FULL_LOOP_STATES
    assert lifecycle["state_trace"][-2:] == [
        "mock_bt009_publication_complete",
        "mock_next_hypothesis_replenished",
    ]


def test_full_loop_rehearsal_fails_closed_on_wrong_worker(tmp_path):
    task = MODULE.build_task("a" * 40)
    workspace = type("Workspace", (), {"artifacts": tmp_path / "artifacts"})()
    receipt = MODULE.mock_terminal_receipt(task, workspace)

    with pytest.raises(RuntimeError, match="generic_coder_is_ineligible"):
        MODULE.rehearse_full_loop_contract(
            task,
            receipt,
            generic_eligible=True,
            dedicated_eligible=True,
        )


def test_provider_capacity_failure_is_structured_and_retryable(tmp_path):
    stderr = tmp_path / "logs/review.stderr.log"
    stderr.parent.mkdir()
    stderr.write_text("ERROR: Selected model is at capacity. Please try again.")
    failed_step = type(
        "Step",
        (),
        {
            "success": False,
            "name": "independent-review",
            "stderr_log": "logs/review.stderr.log",
        },
    )()
    result = type(
        "Result",
        (),
        {"steps": [failed_step], "termination_reason": "step_failed"},
    )()
    plan = type("Plan", (), {"attempt_directory": tmp_path})()
    workspace = type("Workspace", (), {"plan": plan})()

    failure = MODULE.classify_engineering_failure(result, workspace)

    assert failure == {
        "category": "provider_capacity",
        "retryable": True,
        "failed_step": "independent-review",
        "termination_reason": "step_failed",
        "stderr_log": "logs/review.stderr.log",
    }


def test_netlink_sandbox_denial_is_structured(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "coding-agent.stderr.log").write_text(
        "bwrap: loopback: Failed to create NETLINK_ROUTE socket: "
        "Address family not supported by protocol"
    )
    workspace = type("Workspace", (), {"logs": logs})()
    from swarm_worker.executors.code_validation import ExecutionPolicyError

    failure = MODULE.classify_policy_exception(
        ExecutionPolicyError("Coding agent produced no changes."), workspace
    )

    assert failure["category"] == "sandbox_address_family_denied"
    assert failure["retryable"] is False
    assert failure["failed_step"] == "coding-agent"


def test_dedicated_role_and_installer_require_production_parity_rehearsal():
    package = load_role_package(
        ROOT / "role-packages/vm1-alpha-strategy-engineer/manifest.yaml",
        ROOT / "workflows",
    ).manifest
    assert package.risk_ceiling == 1
    assert package.required_capabilities == sorted(MODULE.REQUIRED_CAPABILITIES)

    unit = (
        ROOT / "systemd/invariance-swarm-alpha-strategy-engineer.service"
    ).read_text(encoding="utf-8")
    assert "Environment=NODE_OPTIONS=--jitless" in unit
    assert (
        "Environment=SWARM_CODEX_HOME=/var/lib/invariance-swarm/"
        "codex-alpha-strategy-engineer-runtime" in unit
    )
    assert (
        "BindReadOnlyPaths=/etc/invariance-swarm/codex-worker/auth.json:"
        "/var/lib/invariance-swarm/codex-alpha-strategy-engineer-runtime/auth.json"
        in unit
    )
    assert "MemoryDenyWriteExecute=true" not in unit
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK" in unit

    installer = (
        ROOT / "systemd/install-alpha-strategy-engineer.sh"
    ).read_text(encoding="utf-8")
    rehearsal = installer.index("alpha_loop_rehearsal.py")
    activation = installer.index(
        "systemctl enable --now invariance-swarm-alpha-strategy-engineer.service"
    )
    assert rehearsal < activation
    assert "generic_coder_eligible == false" in installer
    assert ".lifecycle.checks | all(.[]; . == true)" in installer
    assert 'test ! -L "$runtime/auth.json"' in installer
    assert (
        "--codex-home /var/lib/invariance-swarm/"
        "codex-alpha-strategy-engineer-runtime" in installer
    )
    assert "AF_UNIX AF_INET AF_INET6 AF_NETLINK" in installer
