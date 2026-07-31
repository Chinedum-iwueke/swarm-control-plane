from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from swarm_worker.infrastructure.packages import (
    RunbookPackageError,
    load_runbook_package,
    promote_package,
    validate_parameters,
)

ROOT = Path(__file__).parents[1]
PACKAGES = ROOT / "runbook-packages"
UTC = timezone.utc


def test_general_platform_package_covers_standard_operation_categories() -> None:
    package = load_runbook_package(PACKAGES, "vm2-platform-operations")
    categories = {operation.category for operation in package.manifest.operations}
    assert categories == {
        "backup",
        "certificate",
        "docker",
        "health",
        "redis",
        "storage",
    }
    assert all(
        "command" not in operation.model_fields_set
        for operation in package.manifest.operations
    )


def test_invariance_cutover_package_is_private_and_approval_gated() -> None:
    package = load_runbook_package(PACKAGES, "invariance-postgres-cutover")
    production = next(
        profile
        for profile in package.manifest.target_profiles
        if profile.environment == "production"
    )
    cutover = next(
        operation
        for operation in package.manifest.operations
        if operation.name == "cutover-invariance-application"
    )
    assert production.private_endpoint == "100.112.117.59:6432"
    assert production.dns_name == "db.invarianceresearch.internal"
    assert cutover.approval_required is True
    assert cutover.risk_level == 4
    assert cutover.rollback is not None


def test_loader_rejects_path_traversal_and_unknown_fields(tmp_path: Path) -> None:
    with pytest.raises(RunbookPackageError):
        load_runbook_package(PACKAGES, "../outside")

    document = yaml.safe_load(
        (PACKAGES / "vm2-platform-operations.yaml").read_text(encoding="utf-8")
    )
    document["commands"] = ["sudo", "bash", "-c", "anything"]
    path = tmp_path / "vm2-platform-operations.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(RunbookPackageError):
        load_runbook_package(tmp_path, "vm2-platform-operations")


def test_typed_parameters_reject_arbitrary_and_unsafe_values() -> None:
    package = load_runbook_package(PACKAGES, "invariance-postgres-cutover")
    operation = package.manifest.operations[0]
    supplied = validate_parameters(
        operation,
        {
            "dns_name": "db.invarianceresearch.internal",
            "client_cidrs": ["100.64.0.0/10", "10.20.0.0/16"],
        },
    )
    assert supplied["client_cidrs"] == ["100.64.0.0/10", "10.20.0.0/16"]
    with pytest.raises(RunbookPackageError):
        validate_parameters(operation, supplied | {"command": "id"})
    with pytest.raises(RunbookPackageError):
        validate_parameters(
            operation,
            {"dns_name": "$(id)", "client_cidrs": ["100.64.0.0/10"]},
        )
    with pytest.raises(RunbookPackageError):
        validate_parameters(
            operation,
            {"dns_name": "db.internal", "client_cidrs": ["0.0.0.0/0"]},
        )


def test_package_promotion_is_sequential_and_digest_bound() -> None:
    package = load_runbook_package(PACKAGES, "invariance-postgres-cutover")
    now = datetime(2026, 7, 31, tzinfo=UTC)
    draft = promote_package(
        package,
        state="draft",
        recorded_at=now,
        recorded_by="deployment-architect",
    )
    evidence = hashlib.sha256(b"rehearsal-evidence").hexdigest()
    rehearsed = promote_package(
        package,
        state="rehearsed",
        recorded_at=now,
        recorded_by="deployment-architect",
        previous=draft,
        evidence_digest=evidence,
    )
    approved = promote_package(
        package,
        state="approved",
        recorded_at=now,
        recorded_by="founder-operator",
        previous=rehearsed,
        evidence_digest=evidence,
        approval_reference="M10-CUTOVER-APPROVAL",
    )
    assert approved.manifest_digest == package.manifest_digest
    assert approved.previous_record_digest is not None
    with pytest.raises(RunbookPackageError):
        promote_package(
            package,
            state="deployed",
            recorded_at=now,
            recorded_by="deployment-architect",
            previous=draft,
            evidence_digest=evidence,
            approval_reference="M10-CUTOVER-APPROVAL",
        )


def test_approval_cannot_be_reused_after_manifest_change(tmp_path: Path) -> None:
    package = load_runbook_package(PACKAGES, "invariance-postgres-cutover")
    now = datetime(2026, 7, 31, tzinfo=UTC)
    draft = promote_package(
        package,
        state="draft",
        recorded_at=now,
        recorded_by="deployment-architect",
    )
    document = yaml.safe_load(package.source_path.read_text(encoding="utf-8"))
    document["version"] = "1.0.1"
    changed_path = tmp_path / "invariance-postgres-cutover.yaml"
    changed_path.write_text(yaml.safe_dump(document), encoding="utf-8")
    changed = load_runbook_package(tmp_path, "invariance-postgres-cutover")
    with pytest.raises(RunbookPackageError, match="digest"):
        promote_package(
            changed,
            state="rehearsed",
            recorded_at=now,
            recorded_by="deployment-architect",
            previous=draft,
            evidence_digest=hashlib.sha256(b"evidence").hexdigest(),
        )
