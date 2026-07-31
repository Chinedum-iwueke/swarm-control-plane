import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_NAME = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_VERSION = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_COMMIT = r"^[0-9a-f]{40,64}$"
_DIGEST = r"^[0-9a-f]{64}$"


class CompatibilitySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_version_min: str = Field(pattern=_VERSION)
    worker_version_max_exclusive: str = Field(pattern=_VERSION)


class PermissionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    network_access: Literal["none", "control-plane"]
    privileged_operations: bool = False
    writable_roots: list[str] = Field(default_factory=list, max_length=20)


class RepositoryProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repositories: list[str] = Field(default_factory=list, max_length=50)
    primary_checkout_write: bool = False
    remote_write: bool = False


class WorkflowArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    file: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.yaml$")
    sha256: str = Field(pattern=_DIGEST)


class RunbookPackageArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    file: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.yaml$")
    sha256: str = Field(pattern=_DIGEST)


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

    @field_validator(
        "task_types",
        "required_capabilities",
        "allowed_machines",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("values must be unique")
        if any(not re.fullmatch(r"^[a-z0-9][a-z0-9_-]*$", value) for value in values):
            raise ValueError("values must use safe names")
        return values

    @field_validator("workflows")
    @classmethod
    def unique_workflows(
        cls, workflows: list[WorkflowArtifact]
    ) -> list[WorkflowArtifact]:
        if len({workflow.name for workflow in workflows}) != len(workflows):
            raise ValueError("workflow names must be unique")
        return workflows

    @field_validator("runbook_packages")
    @classmethod
    def unique_runbook_packages(
        cls, packages: list[RunbookPackageArtifact]
    ) -> list[RunbookPackageArtifact]:
        if len({package.name for package in packages}) != len(packages):
            raise ValueError("runbook package names must be unique")
        return packages

    @model_validator(mode="after")
    def enforce_restrictions(self) -> "RolePackageManifest":
        if self.permission_profile.privileged_operations:
            raise ValueError("restricted packages cannot request privileged operations")
        if self.repository_profile.primary_checkout_write:
            raise ValueError("primary checkout writes are forbidden")
        if self.repository_profile.remote_write:
            raise ValueError("remote repository writes are forbidden")
        if not self.workflows and self.task_types != ["founder_request"]:
            raise ValueError("only founder_request planner packages may omit workflows")
        if not self.repository_profile.repositories and self.task_types != [
            "founder_request"
        ]:
            raise ValueError("only founder_request planners may omit repositories")
        return self


class RolePackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: RolePackageManifest
    manifest_digest: str = Field(pattern=_DIGEST)
    signature: str = Field(min_length=64, max_length=128)
    source_repository: str = Field(pattern=_NAME)
    source_commit: str = Field(pattern=_COMMIT)
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RolePackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: str
    manifest: RolePackageManifest
    manifest_digest: str
    signature: str
    source_repository: str
    source_commit: str
    created_by: str
    created_at: datetime


class PackageDeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    package_id: uuid.UUID
    deployed_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class PackageDeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    agent_id: uuid.UUID
    package_id: uuid.UUID
    is_active: bool
    deployed_by: str
    deployed_at: datetime
    revoked_at: datetime | None


class AgentPackageDeployment(BaseModel):
    deployment: PackageDeploymentResponse
    package: RolePackageResponse
