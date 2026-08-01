from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from swarm_worker import __version__

_NAME = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_VERSION = r"^[0-9]+\.[0-9]+\.[0-9]+$"


class PackageVerificationError(Exception):
    """A local role package is missing, incompatible, or has changed."""


class CompatibilitySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_version_min: str = Field(pattern=_VERSION)
    worker_version_max_exclusive: str = Field(pattern=_VERSION)


class WorkflowArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    file: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.yaml$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RunbookPackageArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    file: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.yaml$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PermissionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    network_access: Literal["none", "control-plane"]
    privileged_operations: Literal[False]
    writable_roots: list[str] = Field(default_factory=list, max_length=20)


class RepositoryProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repositories: list[str] = Field(default_factory=list, max_length=50)
    primary_checkout_write: Literal[False]
    remote_write: Literal[False]


class RolePackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    name: str = Field(pattern=_NAME)
    version: str = Field(pattern=_VERSION)
    role: str = Field(min_length=1, max_length=150)
    task_types: list[str] = Field(min_length=1, max_length=50)
    workflows: list[WorkflowArtifact] = Field(default_factory=list, max_length=50)
    runbook_packages: list[RunbookPackageArtifact] = Field(
        default_factory=list,
        max_length=50,
    )
    required_capabilities: list[str] = Field(min_length=1, max_length=50)
    allowed_machines: list[str] = Field(min_length=1, max_length=50)
    risk_ceiling: int = Field(ge=0, le=5)
    compatibility: CompatibilitySpec
    permission_profile: PermissionProfile
    repository_profile: RepositoryProfile

    @model_validator(mode="after")
    def validate_profile(self) -> RolePackageManifest:
        if len({item.name for item in self.workflows}) != len(self.workflows):
            raise ValueError("workflow names must be unique")
        if len({item.name for item in self.runbook_packages}) != len(
            self.runbook_packages
        ):
            raise ValueError("runbook package names must be unique")
        non_executing = {
            "founder_request",
            "operational_memory",
            "research_intelligence",
        }
        if not self.workflows and set(self.task_types) - non_executing:
            raise ValueError("only non-executing reasoning packages may omit workflows")
        if (
            not self.repository_profile.repositories
            and set(self.task_types) - non_executing
        ):
            raise ValueError(
                "only non-executing reasoning packages may omit repositories"
            )
        return self


class VerifiedRolePackage(BaseModel):
    manifest: RolePackageManifest
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def canonical_manifest(manifest: RolePackageManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def load_role_package(
    manifest_path: Path,
    workflow_directory: Path,
    runbook_package_directory: Path | None = None,
) -> VerifiedRolePackage:
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest = RolePackageManifest.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise PackageVerificationError("Role package manifest is invalid.") from exc
    if not (
        _version_tuple(manifest.compatibility.worker_version_min)
        <= _version_tuple(__version__)
        < _version_tuple(manifest.compatibility.worker_version_max_exclusive)
    ):
        raise PackageVerificationError("Worker version is incompatible with package.")
    root = workflow_directory.resolve()
    for artifact in manifest.workflows:
        path = (root / artifact.file).resolve()
        if not path.is_relative_to(root):
            raise PackageVerificationError("Workflow path escapes its directory.")
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise PackageVerificationError("Declared workflow is unavailable.") from exc
        if digest != artifact.sha256:
            raise PackageVerificationError(
                f"Workflow digest mismatch for {artifact.name!r}."
            )
    package_root = (
        runbook_package_directory
        if runbook_package_directory is not None
        else workflow_directory.parent / "runbook-packages"
    ).resolve()
    for artifact in manifest.runbook_packages:
        path = (package_root / artifact.file).resolve()
        if not path.is_relative_to(package_root):
            raise PackageVerificationError(
                "Runbook package path escapes its directory."
            )
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise PackageVerificationError(
                "Declared runbook package is unavailable."
            ) from exc
        if digest != artifact.sha256:
            raise PackageVerificationError(
                f"Runbook package digest mismatch for {artifact.name!r}."
            )
    return VerifiedRolePackage(
        manifest=manifest,
        manifest_digest=hashlib.sha256(canonical_manifest(manifest)).hexdigest(),
    )


def _version_tuple(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(_VERSION, value):
        raise PackageVerificationError("Version is not semantic x.y.z.")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]
