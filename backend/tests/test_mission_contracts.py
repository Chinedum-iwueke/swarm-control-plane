import hashlib
import hmac

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas import EngineeringMilestoneManifest
from app.services.missions import canonical_manifest, verify_mission_approval


def manifest_document() -> dict:
    return {
        "schema_version": 1,
        "milestone_id": "M4-PILOT",
        "project": "swarm-control-plane",
        "objective": "Deliver one bounded documentation improvement.",
        "base_ref": "main",
        "source_references": ["docs/PRD.md"],
        "workflow": "engineering-mission",
        "risk_level": 0,
        "allowed_machines": ["vm1-developer"],
        "required_capabilities": ["git", "python", "testing"],
        "budget": {
            "max_tasks": 3,
            "max_attempts_per_task": 1,
            "max_duration_seconds": 1800,
            "max_files_changed": 3,
            "max_diff_lines": 200,
        },
        "work_items": [
            {
                "id": "write-doc",
                "objective": "Add the approved bounded pilot documentation.",
                "depends_on": [],
                "allowed_paths": ["docs"],
                "context_paths": ["README.md"],
                "acceptance_criteria": ["Document is present and accurate."],
                "stop_conditions": ["Requirements conflict."],
            },
            {
                "id": "polish-doc",
                "objective": "Polish the approved pilot documentation wording.",
                "depends_on": ["write-doc"],
                "allowed_paths": ["docs"],
                "context_paths": ["README.md"],
                "acceptance_criteria": ["Document remains accurate."],
                "stop_conditions": ["Requirements conflict."],
            },
        ],
        "deliverables": ["PR bundle"],
        "approved_by": "founder-operator",
        "approval_reference": "M4-PILOT-APPROVAL",
    }


def test_manifest_dag_and_canonical_digest_input() -> None:
    manifest = EngineeringMilestoneManifest.model_validate(manifest_document())
    assert manifest.work_items[1].depends_on == ["write-doc"]
    assert canonical_manifest(manifest) == canonical_manifest(manifest)


def test_cycle_is_rejected() -> None:
    document = manifest_document()
    document["work_items"][0]["depends_on"] = ["polish-doc"]
    with pytest.raises(ValidationError, match="cycle"):
        EngineeringMilestoneManifest.model_validate(document)


def test_unknown_dependency_is_rejected() -> None:
    document = manifest_document()
    document["work_items"][1]["depends_on"] = ["missing"]
    with pytest.raises(ValidationError, match="unknown"):
        EngineeringMilestoneManifest.model_validate(document)


def test_path_traversal_and_unknown_commands_are_rejected() -> None:
    document = manifest_document()
    document["work_items"][0]["allowed_paths"] = ["../etc"]
    document["work_items"][0]["command"] = "curl anything"
    with pytest.raises(ValidationError):
        EngineeringMilestoneManifest.model_validate(document)


def test_task_budget_is_enforced() -> None:
    document = manifest_document()
    document["budget"]["max_tasks"] = 1
    with pytest.raises(ValidationError, match="budget"):
        EngineeringMilestoneManifest.model_validate(document)


def test_founder_approval_signature_is_required() -> None:
    manifest = EngineeringMilestoneManifest.model_validate(manifest_document())
    secret = "founder-mission-secret-value-123456"
    signature = hmac.new(
        secret.encode(), canonical_manifest(manifest), hashlib.sha256
    ).hexdigest()
    verify_mission_approval(manifest, signature, secret)
    with pytest.raises(HTTPException):
        verify_mission_approval(manifest, "0" * 64, secret)
