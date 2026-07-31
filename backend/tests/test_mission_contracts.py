import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas import EngineeringMilestoneManifest, InfrastructureRunbookManifest
from app.services.missions import (
    canonical_manifest,
    refresh_mission,
    verify_mission_approval,
)
from fastapi import HTTPException
from pydantic import ValidationError


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


def infrastructure_manifest_document() -> dict:
    return {
        "schema_version": 1,
        "milestone_id": "VM2-POSTGRES-ROLLOUT",
        "project": "invariance_research",
        "objective": "Deploy the reviewed Postgres runbook through bounded phases.",
        "source_references": ["deploy/ON_PREM_POSTGRES_RUNBOOK.md"],
        "workflow": "infrastructure-runbook",
        "runbook": "vm2-postgres-deployment",
        "runbook_version": "1.0.0",
        "target": "vm2-invariance-postgres",
        "allowed_machines": ["vm2-deployment"],
        "required_capabilities": [
            "deployment-architecture",
            "infrastructure-observation",
            "postgres-deployment",
            "service-health",
        ],
        "budget": {
            "max_tasks": 8,
            "max_attempts_per_task": 1,
            "max_duration_seconds": 21600,
        },
        "phases": [
            {
                "id": "preflight",
                "operation": "preflight-invariance-postgres",
                "objective": "Confirm VM2 is ready for the reviewed deployment.",
                "depends_on": [],
                "risk_level": 0,
                "approval_required": False,
                "acceptance_criteria": ["All mandatory preflight checks pass."],
                "expected_outputs": ["infrastructure-evidence.json"],
            },
            {
                "id": "stage",
                "operation": "stage-invariance-postgres",
                "objective": "Stage reviewed configuration and protected secrets.",
                "depends_on": ["preflight"],
                "risk_level": 2,
                "approval_required": True,
                "acceptance_criteria": ["Staged files match reviewed digests."],
                "expected_outputs": ["infrastructure-evidence.json"],
            },
        ],
        "approved_by": "founder-operator",
        "approval_reference": "VM2-POSTGRES-ROLLOUT-APPROVAL",
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


def test_supervised_engineering_mission_requires_pinned_commit() -> None:
    document = manifest_document()
    document["supervision"] = {
        "mode": "autonomous",
        "approval_mode": "mission_plan",
        "max_auto_recoveries": 1,
        "retry_backoff_seconds": 30,
        "retryable_categories": ["connection_error"],
        "rehearsal_evidence_sha256": "a" * 64,
        "rehearsal_source_commit": "b" * 40,
    }
    with pytest.raises(ValidationError, match="commit-pinned"):
        EngineeringMilestoneManifest.model_validate(document)
    document["base_ref"] = "c" * 40
    assert EngineeringMilestoneManifest.model_validate(document).base_ref == "c" * 40


def test_infrastructure_manifest_enforces_dag_and_phase_policy() -> None:
    manifest = InfrastructureRunbookManifest.model_validate(
        infrastructure_manifest_document()
    )
    assert manifest.phases[1].depends_on == ["preflight"]

    lowered = infrastructure_manifest_document()
    lowered["phases"][1]["risk_level"] = 0
    lowered["phases"][1]["approval_required"] = False
    with pytest.raises(ValidationError, match="risk or approval"):
        InfrastructureRunbookManifest.model_validate(lowered)


def test_infrastructure_manifest_rejects_capability_and_dependency_changes() -> None:
    wrong_capability = infrastructure_manifest_document()
    wrong_capability["required_capabilities"][-1] = "arbitrary-root"
    with pytest.raises(ValidationError, match="capabilities"):
        InfrastructureRunbookManifest.model_validate(wrong_capability)

    cycle = infrastructure_manifest_document()
    cycle["phases"][0]["depends_on"] = ["stage"]
    with pytest.raises(ValidationError, match="cycle"):
        InfrastructureRunbookManifest.model_validate(cycle)


def test_founder_approval_signature_is_required() -> None:
    manifest = EngineeringMilestoneManifest.model_validate(manifest_document())
    secret = "founder-mission-secret-value-123456"
    signature = hmac.new(
        secret.encode(), canonical_manifest(manifest), hashlib.sha256
    ).hexdigest()
    verify_mission_approval(manifest, signature, secret)
    with pytest.raises(HTTPException):
        verify_mission_approval(manifest, "0" * 64, secret)


def test_failed_task_blocks_mission_after_pending_state_is_flushed() -> None:
    mission = SimpleNamespace(
        id="mission-id",
        status="active",
        deadline_at=datetime.now(UTC) + timedelta(minutes=30),
        completed_at=None,
    )
    statuses = MagicMock()
    statuses.all.return_value = ["failed"]
    db = MagicMock()
    db.get.return_value = mission
    db.scalars.return_value = statuses

    refresh_mission(db, mission.id)

    assert db.method_calls[0] == ("flush", (), {})
    assert mission.status == "blocked"
    db.add.assert_called_once()
