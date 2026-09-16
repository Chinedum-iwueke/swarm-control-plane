import hashlib
import hmac
from pathlib import Path

import pytest
import yaml
from app.schemas.package import RolePackageCreate, RolePackageManifest
from app.services.packages import canonical_manifest, verify_package
from fastapi import HTTPException

ROOT = Path(__file__).parents[2]


def manifest() -> RolePackageManifest:
    return RolePackageManifest.model_validate(
        {
            "schema_version": 1,
            "name": "restricted-code-validator",
            "version": "1.0.0",
            "role": "Restricted validator",
            "task_types": ["code_validation"],
            "workflows": [
                {
                    "name": "code-validation",
                    "file": "code-validation.yaml",
                    "sha256": "a" * 64,
                }
            ],
            "required_capabilities": ["git", "python", "testing"],
            "allowed_machines": ["vm1-developer"],
            "risk_ceiling": 1,
            "compatibility": {
                "worker_version_min": "0.2.0",
                "worker_version_max_exclusive": "0.3.0",
            },
            "permission_profile": {
                "name": "restricted-validation",
                "network_access": "control-plane",
                "privileged_operations": False,
                "writable_roots": ["workspace"],
            },
            "repository_profile": {
                "repositories": ["swarm-control-plane"],
                "primary_checkout_write": False,
                "remote_write": False,
            },
        }
    )


def test_digest_and_signature_are_verified() -> None:
    package = manifest()
    document = canonical_manifest(package)
    secret = "s" * 32
    payload = RolePackageCreate(
        manifest=package,
        manifest_digest=hashlib.sha256(document).hexdigest(),
        signature=hmac.new(secret.encode(), document, hashlib.sha256).hexdigest(),
        source_repository="swarm-control-plane",
        source_commit="a" * 40,
        created_by="founder-operator",
    )
    verify_package(payload, secret)
    with pytest.raises(HTTPException):
        verify_package(payload.model_copy(update={"signature": "0" * 64}), secret)


@pytest.mark.parametrize(
    ("role", "capability"),
    [
        ("spec", "alpha-strategy-review-strategy_spec"),
        ("causality", "alpha-strategy-review-causality_leakage"),
    ],
)
def test_exact_alpha_reviewer_manifests_match_api_contract(
    role: str, capability: str
) -> None:
    document = yaml.safe_load(
        (
            ROOT
            / "worker"
            / "role-packages"
            / f"vm1-alpha-{role}-reviewer"
            / "manifest.yaml"
        ).read_text(encoding="utf-8")
    )

    parsed = RolePackageManifest.model_validate(document)

    assert parsed.required_capabilities == [capability]


def test_unsafe_permission_profile_is_rejected() -> None:
    document = manifest().model_dump()
    document["permission_profile"]["privileged_operations"] = True
    with pytest.raises(ValueError):
        RolePackageManifest.model_validate(document)


def test_manifest_has_no_command_surface() -> None:
    assert "command" not in RolePackageManifest.model_fields
    assert "steps" not in RolePackageManifest.model_fields


def test_runbook_package_artifacts_are_digest_bound() -> None:
    document = manifest().model_dump()
    document["runbook_packages"] = [
        {
            "name": "vm2-platform-operations",
            "file": "vm2-platform-operations.yaml",
            "sha256": "b" * 64,
        }
    ]
    parsed = RolePackageManifest.model_validate(document)
    assert parsed.runbook_packages[0].sha256 == "b" * 64

    document["runbook_packages"].append(document["runbook_packages"][0])
    with pytest.raises(ValueError):
        RolePackageManifest.model_validate(document)


def test_workflowless_package_is_limited_to_non_executing_roles() -> None:
    planner = manifest().model_dump()
    planner["task_types"] = ["founder_request"]
    planner["workflows"] = []
    planner["repository_profile"]["repositories"] = []
    parsed = RolePackageManifest.model_validate(planner)
    assert parsed.workflows == []

    planner["task_types"] = ["research_intelligence"]
    parsed = RolePackageManifest.model_validate(planner)
    assert parsed.repository_profile.repositories == []

    planner["task_types"] = ["code_validation"]
    with pytest.raises(ValueError):
        RolePackageManifest.model_validate(planner)
