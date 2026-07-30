from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from swarm_worker import __version__
from swarm_worker.api_client import ConflictError, SwarmAPIClient
from swarm_worker.models import (
    AgentHeartbeat,
    FounderProposalCreate,
    FounderProposalDocument,
    Task,
    TaskCompleteRequest,
    TaskExecutionHeartbeatRequest,
    TaskFailRequest,
    TaskLeaseRequest,
    TaskReleaseRequest,
    TaskStartRequest,
)
from swarm_worker.planner.config import PlannerSettings
from swarm_worker.planner.engine import CodexProposalPlanner, PlannerError
from swarm_worker.role_package import load_role_package

PlannerOutcomeKind = Literal[
    "no_work", "succeeded", "failed", "released", "lease_lost"
]


@dataclass(frozen=True)
class PlannerOutcome:
    kind: PlannerOutcomeKind
    task_id: str | None = None
    proposal_id: str | None = None


class FounderIntakePlannerService:
    def __init__(
        self,
        settings: PlannerSettings,
        *,
        api: SwarmAPIClient,
        planner: CodexProposalPlanner,
    ) -> None:
        self._settings = settings
        self._api = api
        self._planner = planner

    async def run_once(self) -> PlannerOutcome:
        identity = await self._api.get_identity()
        if (
            identity.slug != self._settings.swarm_agent_slug
            or identity.machine != self._settings.swarm_machine
            or not identity.is_enabled
            or "founder-intake" not in identity.capabilities
        ):
            raise PlannerError("Planner identity does not match its configuration.")
        heartbeat = AgentHeartbeat(
            status="idle",
            runtime="hermes-founder-planner",
            runtime_version=__version__,
            capabilities=identity.capabilities,
            metadata=self._package_attestation(),
        )
        await self._api.send_agent_heartbeat(heartbeat)
        lease = await self._api.lease_task(
            TaskLeaseRequest(lease_seconds=self._settings.swarm_lease_seconds)
        )
        if lease.task is None or lease.lease_token is None:
            return PlannerOutcome("no_work")
        task = lease.task
        token = lease.lease_token
        if task.task_type != "founder_request":
            await self._api.release_task(
                task.id,
                TaskReleaseRequest(
                    lease_token=token,
                    message="Founder planner only accepts founder_request tasks.",
                ),
            )
            return PlannerOutcome("released", str(task.id))
        try:
            await self._api.start_task(
                task.id,
                TaskStartRequest(
                    lease_token=token,
                    message="Founder intake proposal planning started.",
                ),
            )
            proposal = await self._plan_with_heartbeats(task, token)
            stored = await self._api.submit_founder_proposal(
                task.id,
                FounderProposalCreate(lease_token=token, proposal=proposal),
            )
            await self._api.complete_task(
                task.id,
                TaskCompleteRequest(
                    lease_token=token,
                    message="Founder intake proposal is ready for review.",
                    result={
                        "proposal_id": str(stored.id),
                        "proposal_digest": stored.proposal_digest,
                        "recommended_action": proposal.recommended_action,
                    },
                ),
            )
            return PlannerOutcome(
                "succeeded", str(task.id), str(stored.id)
            )
        except ConflictError:
            return PlannerOutcome("lease_lost", str(task.id))
        except PlannerError as exc:
            try:
                await self._api.fail_task(
                    task.id,
                    TaskFailRequest(
                        lease_token=token,
                        message="Founder intake planning failed safely.",
                        failure={
                            "error_category": type(exc).__name__,
                            "message": str(exc)[:500],
                        },
                        retryable=False,
                    ),
                )
            except ConflictError:
                return PlannerOutcome("lease_lost", str(task.id))
            return PlannerOutcome("failed", str(task.id))

    async def _plan_with_heartbeats(
        self, task: Task, token: str
    ) -> FounderProposalDocument:
        planning = asyncio.create_task(self._planner.plan(task))
        try:
            while True:
                done, _ = await asyncio.wait(
                    {planning},
                    timeout=self._settings.swarm_task_heartbeat_seconds,
                )
                if planning in done:
                    return planning.result()
                try:
                    await self._api.heartbeat_task(
                        task.id,
                        TaskExecutionHeartbeatRequest(
                            lease_token=token,
                            lease_seconds=self._settings.swarm_lease_seconds,
                            message="Founder intake planning is in progress.",
                            progress={"stage": "proposal_generation"},
                        ),
                    )
                except ConflictError:
                    planning.cancel()
                    try:
                        await planning
                    except asyncio.CancelledError:
                        pass
                    raise
        finally:
            if not planning.done():
                planning.cancel()

    def _package_attestation(self) -> dict[str, str]:
        package = load_role_package(
            self._settings.swarm_role_package_manifest,
            self._settings.swarm_workflow_directory,
        )
        return {
            "role_package": package.manifest.name,
            "role_package_version": package.manifest.version,
            "role_package_digest": package.manifest_digest,
        }
