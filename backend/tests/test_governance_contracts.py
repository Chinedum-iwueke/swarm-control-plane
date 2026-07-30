import pytest
from pydantic import ValidationError

from app.schemas import ApprovalDecision, ArtifactCreate
from app.services.governance import task_plan_digest


def test_plan_digest_is_canonical_and_changes_with_plan() -> None:
    first = task_plan_digest({"workflow": "validate", "risk": 1})
    reordered = task_plan_digest({"risk": 1, "workflow": "validate"})
    changed = task_plan_digest({"workflow": "validate", "risk": 2})
    assert first == reordered
    assert first != changed


def test_artifact_location_is_restricted_to_registered_schemes() -> None:
    common = {
        "lease_token": "lease-token",
        "artifact_type": "log",
        "name": "tests.stdout.log",
        "size_bytes": 10,
        "sha256": "a" * 64,
        "storage_backend": "workspace",
        "workflow": "code-validation",
        "workflow_version": "1.0.0",
        "source_commit": "b" * 40,
    }
    artifact = ArtifactCreate(location="workspace://logs/tests.log", **common)
    assert artifact.location.startswith("workspace://")
    with pytest.raises(ValidationError):
        ArtifactCreate(location="/etc/shadow", **common)


def test_approval_decision_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(
            actor="founder-operator",
            reason="Reviewed",
            expires_in_seconds=300,
            execution_command="sudo anything",
        )
