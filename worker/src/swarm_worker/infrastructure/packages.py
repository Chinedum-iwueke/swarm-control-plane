from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_NAME = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_VERSION = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_SHA256 = r"^[0-9a-f]{64}$"
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class RunbookPackageError(Exception):
    """A runbook package or lifecycle transition failed closed."""


class ParameterDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["string", "integer", "boolean", "cidr-list"]
    required: bool = True
    secret: bool = False
    minimum: int | None = None
    maximum: int | None = None
    allowed_values: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_constraints(self) -> ParameterDefinition:
        if self.type != "integer" and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("numeric limits require an integer parameter")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum cannot exceed maximum")
        if self.type != "string" and self.allowed_values:
            raise ValueError("allowed values require a string parameter")
        return self


class TargetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=_NAME)
    machine: str = Field(pattern=_NAME)
    environment: Literal["rehearsal", "staging", "production"]
    service_class: Literal[
        "platform",
        "docker",
        "redis",
        "postgres",
        "storage",
        "certificate",
        "backup",
        "health",
    ]
    writable_roots: list[str] = Field(default_factory=list, max_length=20)
    private_endpoint: str | None = Field(default=None, max_length=255)
    dns_name: str | None = Field(default=None, max_length=253)


class PreflightContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[str] = Field(min_length=1, max_length=30)
    failure_mode: Literal["block"] = "block"


class RehearsalContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = True
    target_profile: str = Field(pattern=_NAME)
    max_evidence_age_hours: int = Field(ge=1, le=720)
    required_evidence: list[str] = Field(min_length=1, max_length=30)


class RollbackDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str = Field(pattern=_NAME)
    triggers: list[str] = Field(min_length=1, max_length=20)
    timeout_seconds: int = Field(ge=1, le=3600)
    required_evidence: list[str] = Field(min_length=1, max_length=20)


class PackagedOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=_NAME)
    category: Literal[
        "docker", "redis", "postgres", "storage", "certificate", "backup", "health"
    ]
    task_type: Literal["infrastructure_observation", "infrastructure_operation"]
    target_profile: str = Field(pattern=_NAME)
    risk_level: int = Field(ge=0, le=5)
    approval_required: bool
    parameters: dict[str, ParameterDefinition] = Field(default_factory=dict)
    preflight: PreflightContract
    evidence: list[str] = Field(min_length=1, max_length=30)
    rollback: RollbackDefinition | None = None

    @model_validator(mode="after")
    def enforce_mutation_policy(self) -> PackagedOperation:
        if self.task_type == "infrastructure_operation":
            if not self.approval_required or self.rollback is None:
                raise ValueError("mutating operations require approval and rollback")
        elif self.risk_level > 1:
            raise ValueError("observation risk cannot exceed 1")
        return self


class RunbookPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    name: str = Field(pattern=_NAME)
    version: str = Field(pattern=_VERSION)
    description: str = Field(min_length=1, max_length=300)
    target_profiles: list[TargetProfile] = Field(min_length=1, max_length=20)
    rehearsal: RehearsalContract
    operations: list[PackagedOperation] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_references(self) -> RunbookPackageManifest:
        targets = [profile.name for profile in self.target_profiles]
        if len(targets) != len(set(targets)):
            raise ValueError("target profile names must be unique")
        operations = [operation.name for operation in self.operations]
        if len(operations) != len(set(operations)):
            raise ValueError("operation names must be unique")
        if self.rehearsal.target_profile not in targets:
            raise ValueError("rehearsal target profile is undefined")
        if any(operation.target_profile not in targets for operation in self.operations):
            raise ValueError("operation target profile is undefined")
        return self


class VerifiedRunbookPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: RunbookPackageManifest
    manifest_digest: str = Field(pattern=_SHA256)
    source_path: Path


class PromotionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(pattern=_NAME)
    package_version: str = Field(pattern=_VERSION)
    manifest_digest: str = Field(pattern=_SHA256)
    state: Literal["draft", "rehearsed", "approved", "deployed"]
    recorded_at: datetime
    recorded_by: str = Field(min_length=1, max_length=100)
    evidence_digest: str | None = Field(default=None, pattern=_SHA256)
    approval_reference: str | None = Field(default=None, min_length=1, max_length=150)
    previous_record_digest: str | None = Field(default=None, pattern=_SHA256)

    @model_validator(mode="after")
    def required_state_evidence(self) -> PromotionRecord:
        if self.state != "draft" and self.evidence_digest is None:
            raise ValueError("promoted states require evidence")
        if self.state in {"approved", "deployed"} and not self.approval_reference:
            raise ValueError("approved states require an approval reference")
        return self


def canonical_manifest(manifest: RunbookPackageManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def promotion_digest(record: PromotionRecord) -> str:
    canonical = json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def load_runbook_package(directory: Path, name: str) -> VerifiedRunbookPackage:
    if not re.fullmatch(_NAME, name):
        raise RunbookPackageError("Runbook package name is unsafe.")
    root = directory.resolve()
    path = (root / f"{name}.yaml").resolve()
    if not path.is_relative_to(root):
        raise RunbookPackageError("Runbook package path escapes its directory.")
    try:
        document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest = RunbookPackageManifest.model_validate(document)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise RunbookPackageError("Runbook package is unavailable or invalid.") from exc
    if manifest.name != name:
        raise RunbookPackageError("Runbook package name does not match its file.")
    return VerifiedRunbookPackage(
        manifest=manifest,
        manifest_digest=hashlib.sha256(canonical_manifest(manifest)).hexdigest(),
        source_path=path,
    )


def validate_parameters(
    operation: PackagedOperation,
    supplied: dict[str, Any],
) -> dict[str, Any]:
    unknown = set(supplied) - set(operation.parameters)
    missing = {
        name
        for name, definition in operation.parameters.items()
        if definition.required and name not in supplied
    }
    if unknown or missing:
        raise RunbookPackageError("Operation parameters do not match the contract.")
    validated: dict[str, Any] = {}
    for name, value in supplied.items():
        definition = operation.parameters[name]
        validated[name] = _validate_parameter(name, definition, value)
    return validated


def promote_package(
    package: VerifiedRunbookPackage,
    *,
    state: Literal["draft", "rehearsed", "approved", "deployed"],
    recorded_at: datetime,
    recorded_by: str,
    previous: PromotionRecord | None = None,
    evidence_digest: str | None = None,
    approval_reference: str | None = None,
) -> PromotionRecord:
    states = ("draft", "rehearsed", "approved", "deployed")
    if previous is not None and previous.state == "deployed":
        raise RunbookPackageError("A deployed package has no further promotion state.")
    expected = (
        states[0]
        if previous is None
        else states[states.index(previous.state) + 1]
    )
    if state != expected:
        raise RunbookPackageError("Runbook package promotion must be sequential.")
    if previous is not None and (
        previous.package_name != package.manifest.name
        or previous.package_version != package.manifest.version
        or previous.manifest_digest != package.manifest_digest
    ):
        raise RunbookPackageError("Promotion record does not match package digest.")
    return PromotionRecord(
        package_name=package.manifest.name,
        package_version=package.manifest.version,
        manifest_digest=package.manifest_digest,
        state=state,
        recorded_at=recorded_at,
        recorded_by=recorded_by,
        evidence_digest=evidence_digest,
        approval_reference=approval_reference,
        previous_record_digest=(promotion_digest(previous) if previous else None),
    )


def _validate_parameter(
    name: str,
    definition: ParameterDefinition,
    value: Any,
) -> Any:
    if definition.type == "boolean":
        if not isinstance(value, bool):
            raise RunbookPackageError(f"Parameter {name!r} must be boolean.")
        return value
    if definition.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise RunbookPackageError(f"Parameter {name!r} must be an integer.")
        if definition.minimum is not None and value < definition.minimum:
            raise RunbookPackageError(f"Parameter {name!r} is below its minimum.")
        if definition.maximum is not None and value > definition.maximum:
            raise RunbookPackageError(f"Parameter {name!r} exceeds its maximum.")
        return value
    if definition.type == "cidr-list":
        import ipaddress

        if not isinstance(value, list) or not value:
            raise RunbookPackageError(f"Parameter {name!r} must be a CIDR list.")
        try:
            networks = [ipaddress.ip_network(item, strict=True) for item in value]
        except (TypeError, ValueError) as exc:
            raise RunbookPackageError(f"Parameter {name!r} contains invalid CIDR.") from exc
        if any(
            network.prefixlen < (8 if network.version == 4 else 32)
            for network in networks
        ):
            raise RunbookPackageError(f"Parameter {name!r} is too broad.")
        return [str(network) for network in networks]
    if not isinstance(value, str) or not _SAFE_VALUE.fullmatch(value):
        raise RunbookPackageError(f"Parameter {name!r} is unsafe.")
    if definition.allowed_values and value not in definition.allowed_values:
        raise RunbookPackageError(f"Parameter {name!r} is not allowlisted.")
    return value
