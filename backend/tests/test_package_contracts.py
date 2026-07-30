import hashlib
import hmac

import pytest
from fastapi import HTTPException

from app.schemas.package import RolePackageCreate, RolePackageManifest
from app.services.packages import canonical_manifest, verify_package


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


def test_unsafe_permission_profile_is_rejected() -> None:
    document = manifest().model_dump()
    document["permission_profile"]["privileged_operations"] = True
    with pytest.raises(ValueError):
        RolePackageManifest.model_validate(document)


def test_manifest_has_no_command_surface() -> None:
    assert "command" not in RolePackageManifest.model_fields
    assert "steps" not in RolePackageManifest.model_fields
