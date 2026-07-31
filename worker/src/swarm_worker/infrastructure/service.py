from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import ValidationError

from swarm_worker import __version__
from swarm_worker.api_client import (
    AuthenticationError,
    ConflictError,
    SwarmAPIClient,
)
from swarm_worker.infrastructure.client import BrokerClient, BrokerClientError
from swarm_worker.infrastructure.config import InfrastructureSettings
from swarm_worker.infrastructure.packages import (
    load_runbook_package,
    validate_parameters,
)
from swarm_worker.infrastructure.runbooks import load_runbook
from swarm_worker.models import (
    AgentHeartbeat,
    ArtifactCreateRequest,
    BrokerExecutionResult,
    BrokerTicketRequest,
    InfrastructureContract,
    TaskCompleteRequest,
    TaskExecutionHeartbeatRequest,
    TaskFailRequest,
    TaskLeaseRequest,
    TaskReleaseRequest,
    TaskStartRequest,
)
from swarm_worker.role_package import load_role_package


class InfrastructureServiceError(Exception):
    """A restricted infrastructure cycle failed outside task execution."""


class InfrastructureOutcome:
    def __init__(
        self,
        status: Literal["no_work", "succeeded", "failed", "released", "lease_lost"],
        task_id: str | None = None,
    ) -> None:
        self.status = status
        self.task_id = task_id


class InfrastructureService:
    def __init__(
        self,
        settings: InfrastructureSettings,
        *,
        api_factory=SwarmAPIClient,
        broker_factory=BrokerClient,
    ) -> None:
        self._settings = settings
        self._api_factory = api_factory
        self._broker_factory = broker_factory

    async def run_once(self) -> InfrastructureOutcome:
        settings = self._settings
        settings.prepare_directories()
        package = load_role_package(
            settings.swarm_infrastructure_role_manifest,
            settings.swarm_infrastructure_runbook_directory,
            settings.swarm_infrastructure_package_directory,
        )
        packaged_operations = {}
        for artifact in package.manifest.runbook_packages:
            loaded = load_runbook_package(
                settings.swarm_infrastructure_package_directory,
                artifact.name,
            )
            if loaded.source_path.name != artifact.file:
                raise InfrastructureServiceError(
                    "Attested runbook package filename mismatch."
                )
            packaged_operations.update(
                {
                    operation.name: (operation, loaded)
                    for operation in loaded.manifest.operations
                }
            )
        operations = {
            operation.name: operation
            for artifact in package.manifest.workflows
            for operation in load_runbook(
                settings.swarm_infrastructure_runbook_directory / artifact.file
            ).operations
        }
        api = self._api_factory(settings)
        task = None
        lease_token = None
        started = False
        try:
            identity = await api.get_identity()
            if (
                not identity.is_enabled
                or identity.slug != settings.swarm_agent_slug
                or identity.machine != settings.swarm_machine
            ):
                raise InfrastructureServiceError("Agent identity mismatch.")
            manifest = package.manifest
            if (
                settings.swarm_machine not in manifest.allowed_machines
                or not set(manifest.required_capabilities).issubset(
                    identity.capabilities
                )
                or identity.risk_ceiling < manifest.risk_ceiling
            ):
                raise InfrastructureServiceError("Role package mismatch.")
            await api.send_agent_heartbeat(
                AgentHeartbeat(
                    status="idle",
                    runtime="hermes-infrastructure",
                    runtime_version=__version__,
                    capabilities=identity.capabilities,
                    metadata={
                        "agent_slug": identity.slug,
                        "machine": identity.machine,
                        "worker_version": __version__,
                        "role_package": manifest.name,
                        "role_package_version": manifest.version,
                        "role_package_digest": package.manifest_digest,
                    },
                )
            )
            lease = await api.lease_task(
                TaskLeaseRequest(lease_seconds=settings.swarm_lease_seconds)
            )
            if lease.task is None and lease.lease_token is None:
                return InfrastructureOutcome("no_work")
            if lease.task is None or lease.lease_token is None:
                raise InfrastructureServiceError("Incomplete task lease.")
            task = lease.task
            lease_token = lease.lease_token
            try:
                contract = self._validate_task(
                    task,
                    manifest,
                    operations,
                    packaged_operations,
                    identity,
                )
            except InfrastructureServiceError as exc:
                await api.release_task(
                    task.id,
                    TaskReleaseRequest(
                        lease_token=lease_token,
                        message=f"Infrastructure worker policy rejection: {type(exc).__name__}.",
                    ),
                )
                return InfrastructureOutcome("released", str(task.id))
            await api.start_task(
                task.id,
                TaskStartRequest(
                    lease_token=lease_token,
                    message="Restricted infrastructure operation started.",
                ),
            )
            started = True
            ticket = await api.get_broker_ticket(
                task.id, BrokerTicketRequest(lease_token=lease_token)
            )
            broker = self._broker_factory(settings.swarm_broker_socket)
            result = await self._execute_with_heartbeats(
                api,
                broker,
                ticket,
                task.id,
                lease_token,
                contract.operation,
            )
            evidence_path, digest = self._write_evidence(task, result)
            await api.register_artifact(
                task.id,
                ArtifactCreateRequest(
                    lease_token=lease_token,
                    artifact_type="evidence",
                    name="infrastructure-evidence.json",
                    size_bytes=evidence_path.stat().st_size,
                    sha256=digest,
                    location="workspace://artifacts/infrastructure-evidence.json",
                    storage_backend="workspace",
                    workflow=contract.operation,
                    workflow_version=contract.runbook_version,
                    source_commit=settings.swarm_source_commit,
                    confidentiality="internal",
                    retention_class="audit",
                    metadata={"operation": contract.operation},
                ),
            )
            summary = self._bounded_summary(result, digest)
            if result.success:
                await api.complete_task(
                    task.id,
                    TaskCompleteRequest(
                        lease_token=lease_token,
                        message="Restricted infrastructure operation succeeded.",
                        result=summary,
                    ),
                )
                return InfrastructureOutcome("succeeded", str(task.id))
            await api.fail_task(
                task.id,
                TaskFailRequest(
                    lease_token=lease_token,
                    message="Restricted infrastructure operation failed.",
                    failure=summary,
                    retryable=False,
                ),
            )
            return InfrastructureOutcome("failed", str(task.id))
        except (AuthenticationError, ConflictError):
            if task is not None and started:
                return InfrastructureOutcome("lease_lost", str(task.id))
            raise
        except (BrokerClientError, OSError, ValidationError) as exc:
            if task is not None and lease_token is not None and started:
                try:
                    await api.fail_task(
                        task.id,
                        TaskFailRequest(
                            lease_token=lease_token,
                            message="Infrastructure broker execution failed.",
                            failure={
                                "error_category": type(exc).__name__,
                                "retryable": False,
                            },
                            retryable=False,
                        ),
                    )
                except (AuthenticationError, ConflictError):
                    return InfrastructureOutcome("lease_lost", str(task.id))
                return InfrastructureOutcome("failed", str(task.id))
            raise
        finally:
            await api.aclose()

    async def _execute_with_heartbeats(
        self,
        api,
        broker,
        ticket,
        task_id,
        lease_token: str,
        operation: str,
    ) -> BrokerExecutionResult:
        execution = asyncio.create_task(broker.execute(ticket))

        async def heartbeat() -> None:
            while not execution.done():
                await api.heartbeat_task(
                    task_id,
                    TaskExecutionHeartbeatRequest(
                        lease_token=lease_token,
                        lease_seconds=self._settings.swarm_lease_seconds,
                        message="Restricted infrastructure operation is running.",
                        progress={"operation": operation, "phase": "broker_execution"},
                    ),
                )
                await asyncio.sleep(
                    self._settings.swarm_task_heartbeat_seconds
                )

        heartbeats = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait(
                {execution, heartbeats},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeats in done:
                exception = heartbeats.exception()
                if exception is not None:
                    execution.cancel()
                    await asyncio.gather(execution, return_exceptions=True)
                    raise exception
            return await execution
        finally:
            heartbeats.cancel()
            await asyncio.gather(heartbeats, return_exceptions=True)

    @staticmethod
    def _validate_task(
        task, manifest, operations, packaged_operations, identity
    ) -> InfrastructureContract:
        if task.task_type not in manifest.task_types:
            raise InfrastructureServiceError("Task type is not in role package.")
        try:
            contract = InfrastructureContract.model_validate(task.input_contract)
        except ValidationError as exc:
            raise InfrastructureServiceError(
                "Infrastructure contract is invalid."
            ) from exc
        legacy_expected = {
            "observe-control-plane": ("infrastructure_observation", 0),
            "restart-control-plane-api": ("infrastructure_operation", 3),
            "preflight-invariance-postgres": (
                "infrastructure_observation",
                0,
            ),
            "stage-invariance-postgres": ("infrastructure_operation", 2),
            "start-invariance-postgres-private": (
                "infrastructure_operation",
                3,
            ),
            "initialize-invariance-schema": ("infrastructure_operation", 3),
            "configure-invariance-backups": ("infrastructure_operation", 3),
            "verify-invariance-postgres": (
                "infrastructure_observation",
                0,
            ),
            "prepare-invariance-cutover": (
                "infrastructure_observation",
                0,
            ),
        }
        if contract.runbook == "vm2-platform-operations":
            packaged = packaged_operations.get(contract.operation)
            if packaged is None:
                raise InfrastructureServiceError("Packaged operation is unavailable.")
            definition, package = packaged
            if (
                contract.package_name != package.manifest.name
                or contract.package_version != package.manifest.version
                or contract.package_digest != package.manifest_digest
                or contract.target != definition.target_profile
                or task.task_type != definition.task_type
                or task.risk_level != definition.risk_level
            ):
                raise InfrastructureServiceError(
                    "Task does not match packaged operation policy."
                )
            try:
                validate_parameters(definition, contract.parameters)
            except Exception as exc:
                raise InfrastructureServiceError(
                    "Packaged operation parameters are invalid."
                ) from exc
            expected = (definition.task_type, definition.risk_level)
        else:
            try:
                expected = legacy_expected[contract.operation]
            except KeyError as exc:
                raise InfrastructureServiceError(
                    "Operation requires an attested runbook package."
                ) from exc
        definition = operations.get(contract.operation)
        if contract.runbook == "vm2-platform-operations":
            definition = SimpleNamespace(
                task_type=expected[0],
                risk_level=expected[1],
                target=contract.target,
            )
        if (
            definition is None
            or definition.task_type != expected[0]
            or definition.risk_level != expected[1]
            or definition.target != contract.target
            or task.task_type != expected[0]
            or task.risk_level != expected[1]
            or task.allowed_machines != ["vm2-deployment"]
            or not set(task.required_capabilities).issubset(identity.capabilities)
            or task.risk_level > identity.risk_ceiling
            or task.attempt_count < 1
        ):
            raise InfrastructureServiceError("Task does not match operation policy.")
        return contract

    def _write_evidence(self, task, result: BrokerExecutionResult) -> tuple[Path, str]:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", task.task_number)[:80]
        attempt = (
            self._settings.swarm_infrastructure_workspace_root
            / f"{safe}-{task.id}"
            / f"attempt-{task.attempt_count}"
        )
        artifacts = attempt / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=False, mode=0o700)
        path = artifacts / "infrastructure-evidence.json"
        content = (
            json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        )
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        return path, hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _bounded_summary(
        result: BrokerExecutionResult, digest: str
    ) -> dict[str, object]:
        latest = result.pre_state.get("latest_backup")
        post = result.post_state or {}
        action_codes = {
            name: value.get("return_code")
            for name, value in (result.action or {}).items()
            if isinstance(value, dict) and "return_code" in value
        }
        return {
            "success": result.success,
            "operation": result.operation,
            "attempt": result.attempt_number,
            "started_at": result.started_at.isoformat(),
            "ended_at": result.ended_at.isoformat(),
            "pre_healthy": bool(
                result.pre_state.get("healthy", result.pre_state.get("ready"))
            ),
            "preflight_checks": (
                result.pre_state.get("checks")
                if result.operation == "preflight-invariance-postgres"
                else None
            ),
            "public_tls": (
                result.pre_state.get("public_tls")
                if result.operation == "preflight-invariance-postgres"
                else None
            ),
            "post_healthy": (
                bool(post.get("healthy")) if result.post_state is not None else None
            ),
            "readiness": (
                {
                    "ready": bool(post.get("ready")),
                    "checks": post.get("checks"),
                    "public_access_changed": post.get("public_access_changed"),
                }
                if result.operation == "prepare-invariance-cutover"
                else None
            ),
            "private_network": (
                {
                    "public_access": post.get("public_access"),
                    "bindings": post.get("bindings"),
                }
                if result.operation
                in {
                    "start-invariance-postgres-private",
                    "verify-invariance-postgres",
                }
                else None
            ),
            "schema_marker": post.get("schema_marker"),
            "backup": post.get("backup", post.get("latest_backup")),
            "restore_drill": post.get("restore_drill"),
            "latest_backup": latest if isinstance(latest, dict) else None,
            "action_return_code": (
                result.action.get("return_code") if result.action else None
            ),
            "action_return_codes": action_codes,
            "rollback_attempted": result.rollback is not None,
            "rollback_return_code": (
                result.rollback.get("return_code") if result.rollback else None
            ),
            "rollback_healthy": (
                bool(result.rollback_state.get("healthy"))
                if result.rollback_state is not None
                else None
            ),
            "evidence": "artifacts/infrastructure-evidence.json",
            "evidence_sha256": digest,
        }
