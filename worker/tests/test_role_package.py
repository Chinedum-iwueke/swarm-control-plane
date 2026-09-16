import hashlib
from pathlib import Path

import pytest
import yaml

from swarm_worker.role_package import PackageVerificationError, load_role_package

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "role-packages/vm1-engineering-worker/manifest.yaml"
WORKFLOWS = ROOT / "workflows"
RESEARCH_MANIFEST = ROOT / "role-packages/vm1-research-runner/manifest.yaml"
ALPHA_MANIFEST = ROOT / "role-packages/vm1-alpha-research-executor/manifest.yaml"
MEMORY_MANIFEST = ROOT / "role-packages/vm1-research-memory-steward/manifest.yaml"
DEPLOYMENT_MANIFEST = ROOT / "role-packages/vm2-deployment-architect/manifest.yaml"
OPERATIONAL_MEMORY_MANIFEST = (
    ROOT / "role-packages/vm1-operational-memory-steward/manifest.yaml"
)
EXEC1_FLEET_MANIFEST = ROOT / "role-packages/exec1-fleet-observer/manifest.yaml"
EXEC2_FLEET_MANIFEST = (
    ROOT / "role-packages/exec2-lagos-fleet-observer/manifest.yaml"
)


def test_versioned_package_and_workflow_digest_verify() -> None:
    package = load_role_package(MANIFEST, WORKFLOWS)
    assert package.manifest.name == "vm1-engineering-worker"
    assert package.manifest.version == "1.0.1"
    assert len(package.manifest_digest) == 64


def test_research_package_is_narrow_and_digest_verified() -> None:
    package = load_role_package(RESEARCH_MANIFEST, WORKFLOWS)
    assert package.manifest.name == "vm1-research-runner"
    assert package.manifest.task_types == ["research_experiment"]
    assert package.manifest.repository_profile.repositories == ["bulletproof_bt"]
    assert package.manifest.permission_profile.privileged_operations is False
    assert package.manifest.permission_profile.network_access == "control-plane"


def test_alpha_executor_package_is_no_capital_and_single_purpose() -> None:
    package = load_role_package(ALPHA_MANIFEST, WORKFLOWS)
    assert package.manifest.task_types == ["alpha_research_execution"]
    assert package.manifest.required_capabilities == [
        "alpha-research-execution",
        "backtesting",
        "research-audit",
    ]
    assert package.manifest.risk_ceiling == 0
    assert package.manifest.repository_profile.repositories == ["bulletproof_bt"]
    assert package.manifest.repository_profile.primary_checkout_write is False
    assert package.manifest.repository_profile.remote_write is False


def test_independent_strategy_review_packages_have_distinct_narrow_identities() -> None:
    packages = []
    for role, kind in (("spec", "strategy_spec"), ("causality", "causality_leakage")):
        package = load_role_package(
            ROOT / f"role-packages/vm1-alpha-{role}-reviewer/manifest.yaml", WORKFLOWS
        )
        packages.append(package)
        assert package.manifest.task_types == ["alpha_strategy_review"]
        assert package.manifest.required_capabilities == [f"alpha-strategy-review:{kind}"]
        assert package.manifest.risk_ceiling == 0
        assert package.manifest.repository_profile.repositories == ["bulletproof_bt"]
        assert package.manifest.repository_profile.primary_checkout_write is False
        assert package.manifest.repository_profile.remote_write is False
        assert package.manifest.permission_profile.privileged_operations is False
    assert packages[0].manifest_digest != packages[1].manifest_digest


def test_memory_steward_is_read_only_and_single_purpose() -> None:
    package = load_role_package(MEMORY_MANIFEST, WORKFLOWS)
    assert package.manifest.task_types == ["research_memory_sync"]
    assert package.manifest.required_capabilities == [
        "git",
        "python",
        "research-memory-sync",
    ]
    assert package.manifest.repository_profile.repositories == ["bulletproof_bt"]
    assert package.manifest.repository_profile.primary_checkout_write is False
    assert package.manifest.repository_profile.remote_write is False


def test_operational_memory_steward_is_non_executing() -> None:
    package = load_role_package(OPERATIONAL_MEMORY_MANIFEST, WORKFLOWS)
    assert package.manifest.task_types == ["operational_memory"]
    assert package.manifest.workflows == []
    assert package.manifest.required_capabilities == ["operational-memory"]
    assert package.manifest.permission_profile.writable_roots == []
    assert package.manifest.repository_profile.repositories == []
    assert package.manifest.permission_profile.privileged_operations is False


def test_exec1_fleet_observer_is_read_only_and_machine_bound() -> None:
    package = load_role_package(EXEC1_FLEET_MANIFEST, WORKFLOWS)
    assert package.manifest.allowed_machines == ["exec1-execution"]
    assert package.manifest.task_types == ["fleet_observation"]
    assert package.manifest.repository_profile.repositories == []
    assert package.manifest.repository_profile.remote_write is False
    assert package.manifest.permission_profile.privileged_operations is False


def test_exec2_fleet_observer_is_read_only_and_machine_bound() -> None:
    package = load_role_package(EXEC2_FLEET_MANIFEST, WORKFLOWS)
    assert package.manifest.allowed_machines == ["exec2-lagos"]
    assert package.manifest.task_types == ["fleet_observation"]
    assert package.manifest.repository_profile.repositories == []
    assert package.manifest.repository_profile.remote_write is False
    assert package.manifest.permission_profile.privileged_operations is False


def test_deployment_architect_attests_runbook_package_digests() -> None:
    package = load_role_package(
        DEPLOYMENT_MANIFEST,
        ROOT / "infrastructure-runbooks",
        ROOT / "runbook-packages",
    )
    assert package.manifest.version == "1.2.0"
    assert {item.name for item in package.manifest.runbook_packages} == {
        "invariance-postgres-cutover",
        "vm2-platform-operations",
    }


def test_tampered_runbook_package_is_rejected(tmp_path: Path) -> None:
    source = ROOT / "runbook-packages"
    for path in source.iterdir():
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / "invariance-postgres-cutover.yaml").write_text(
        "tampered: true\n",
        encoding="utf-8",
    )
    with pytest.raises(PackageVerificationError, match="digest mismatch"):
        load_role_package(
            DEPLOYMENT_MANIFEST,
            ROOT / "infrastructure-runbooks",
            tmp_path,
        )


def test_tampered_workflow_is_rejected(tmp_path: Path) -> None:
    workflow = tmp_path / "code-validation.yaml"
    workflow.write_text("name: changed\n", encoding="utf-8")
    with pytest.raises(PackageVerificationError, match="digest mismatch"):
        load_role_package(MANIFEST, tmp_path)


def test_unknown_manifest_field_is_rejected(tmp_path: Path) -> None:
    document = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    document["commands"] = ["arbitrary"]
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(PackageVerificationError):
        load_role_package(manifest, WORKFLOWS)


def test_incompatible_worker_version_is_rejected(tmp_path: Path) -> None:
    document = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    document["compatibility"]["worker_version_min"] = "9.0.0"
    document["workflows"][0]["sha256"] = hashlib.sha256(
        (WORKFLOWS / "code-validation.yaml").read_bytes()
    ).hexdigest()
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(PackageVerificationError, match="incompatible"):
        load_role_package(manifest, WORKFLOWS)


def test_privileged_profile_is_rejected(tmp_path: Path) -> None:
    document = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    document["permission_profile"]["privileged_operations"] = True
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(PackageVerificationError):
        load_role_package(manifest, WORKFLOWS)
