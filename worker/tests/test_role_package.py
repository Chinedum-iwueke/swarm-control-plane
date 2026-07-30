import hashlib
from pathlib import Path

import pytest
import yaml

from swarm_worker.role_package import PackageVerificationError, load_role_package

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "role-packages/vm1-engineering-worker/manifest.yaml"
WORKFLOWS = ROOT / "workflows"
RESEARCH_MANIFEST = ROOT / "role-packages/vm1-research-runner/manifest.yaml"


def test_versioned_package_and_workflow_digest_verify() -> None:
    package = load_role_package(MANIFEST, WORKFLOWS)
    assert package.manifest.name == "vm1-engineering-worker"
    assert package.manifest.version == "1.0.0"
    assert len(package.manifest_digest) == 64


def test_research_package_is_narrow_and_digest_verified() -> None:
    package = load_role_package(RESEARCH_MANIFEST, WORKFLOWS)
    assert package.manifest.name == "vm1-research-runner"
    assert package.manifest.task_types == ["research_experiment"]
    assert package.manifest.repository_profile.repositories == ["bulletproof_bt"]
    assert package.manifest.permission_profile.privileged_operations is False
    assert package.manifest.permission_profile.network_access == "control-plane"


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
