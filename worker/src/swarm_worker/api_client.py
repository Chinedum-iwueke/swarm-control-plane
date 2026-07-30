import json
from types import TracebackType
from typing import Any, TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from typing_extensions import Self

from swarm_worker.config import WorkerSettings
from swarm_worker.models import (
    AgentHeartbeat,
    AgentHeartbeatResponse,
    AgentIdentity,
    ArtifactCreateRequest,
    ArtifactResponse,
    BrokerTicketRequest,
    BrokerTicketResponse,
    LeaseResponse,
    TaskCompleteRequest,
    TaskExecutionHeartbeatRequest,
    TaskFailRequest,
    TaskLeaseRequest,
    TaskMutationResponse,
    TaskReleaseRequest,
    TaskStartRequest,
)

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class WorkerAPIError(Exception):
    """Base class for failures while communicating with the control plane."""


class AuthenticationError(WorkerAPIError):
    """The agent or lease credential was rejected."""


class ConflictError(WorkerAPIError):
    """The requested task transition conflicts with current server state."""


class ValidationError(WorkerAPIError):
    """The control plane rejected the request body."""


class ConnectionError(WorkerAPIError):
    """The control plane could not be reached before the request deadline."""


class ServerError(WorkerAPIError):
    """The control plane returned an unexpected server failure."""


class UnexpectedResponseError(WorkerAPIError):
    """The control plane returned another unexpected response."""


class ResponseValidationError(WorkerAPIError):
    """A successful response did not match the published API contract."""


class SwarmAPIClient:
    def __init__(
        self,
        settings: WorkerSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._agent_token = settings.swarm_agent_token
        self._client = httpx.AsyncClient(
            base_url=settings.swarm_api_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {self._agent_token}",
                "Accept": "application/json",
            },
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_identity(self) -> AgentIdentity:
        return await self._request("GET", "/v1/agent/me", AgentIdentity)

    async def send_agent_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeatResponse:
        return await self._request(
            "POST",
            "/v1/agent/heartbeat",
            AgentHeartbeatResponse,
            payload=heartbeat,
        )

    async def lease_task(
        self,
        request: TaskLeaseRequest,
    ) -> LeaseResponse:
        return await self._request(
            "POST",
            "/v1/agent/tasks/lease",
            LeaseResponse,
            payload=request,
        )

    async def start_task(
        self,
        task_id: UUID | str,
        request: TaskStartRequest,
    ) -> TaskMutationResponse:
        return await self._task_mutation(task_id, "start", request)

    async def heartbeat_task(
        self,
        task_id: UUID | str,
        request: TaskExecutionHeartbeatRequest,
    ) -> TaskMutationResponse:
        return await self._task_mutation(task_id, "heartbeat", request)

    async def complete_task(
        self,
        task_id: UUID | str,
        request: TaskCompleteRequest,
    ) -> TaskMutationResponse:
        return await self._task_mutation(task_id, "complete", request)

    async def fail_task(
        self,
        task_id: UUID | str,
        request: TaskFailRequest,
    ) -> TaskMutationResponse:
        return await self._task_mutation(task_id, "fail", request)

    async def release_task(
        self,
        task_id: UUID | str,
        request: TaskReleaseRequest,
    ) -> TaskMutationResponse:
        return await self._task_mutation(task_id, "release", request)

    async def register_artifact(
        self,
        task_id: UUID | str,
        request: ArtifactCreateRequest,
    ) -> ArtifactResponse:
        return await self._request(
            "POST",
            f"/v1/agent/tasks/{task_id}/artifacts",
            ArtifactResponse,
            payload=request,
            secrets=(request.lease_token,),
        )

    async def get_broker_ticket(
        self,
        task_id: UUID | str,
        request: BrokerTicketRequest,
    ) -> BrokerTicketResponse:
        return await self._request(
            "POST",
            f"/v1/agent/tasks/{task_id}/broker-ticket",
            BrokerTicketResponse,
            payload=request,
            secrets=(request.lease_token,),
        )

    async def _task_mutation(
        self,
        task_id: UUID | str,
        action: str,
        request: BaseModel,
    ) -> TaskMutationResponse:
        return await self._request(
            "POST",
            f"/v1/agent/tasks/{task_id}/{action}",
            TaskMutationResponse,
            payload=request,
            secrets=(self._lease_token(request),),
        )

    async def _request(
        self,
        method: str,
        path: str,
        response_model: type[ResponseModel],
        *,
        payload: BaseModel | None = None,
        secrets: tuple[str, ...] = (),
    ) -> ResponseModel:
        try:
            response = await self._client.request(
                method,
                path,
                json=(payload.model_dump(mode="json") if payload is not None else None),
            )
        except httpx.RequestError as exc:
            raise ConnectionError(
                f"Control-plane request failed: {type(exc).__name__}"
            ) from exc

        if response.is_error:
            self._raise_for_status(response, secrets=secrets)

        try:
            return response_model.model_validate(response.json())
        except (json.JSONDecodeError, PydanticValidationError) as exc:
            raise ResponseValidationError(
                "Control-plane response did not match the API contract."
            ) from exc

    def _raise_for_status(
        self,
        response: httpx.Response,
        *,
        secrets: tuple[str, ...],
    ) -> None:
        detail = self._error_detail(response)
        detail = self._redact(detail, (self._agent_token, *secrets))
        message = f"Control plane returned HTTP {response.status_code}: {detail}"

        if response.status_code in (401, 403):
            raise AuthenticationError(message)
        if response.status_code == 409:
            raise ConflictError(message)
        if response.status_code == 422:
            raise ValidationError(message)
        if response.status_code >= 500:
            raise ServerError(message)
        raise UnexpectedResponseError(message)

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            body: Any = response.json()
        except json.JSONDecodeError:
            return response.text or response.reason_phrase

        if isinstance(body, dict) and "detail" in body:
            body = body["detail"]
        if isinstance(body, str):
            return body
        return json.dumps(body, ensure_ascii=True, sort_keys=True)

    @staticmethod
    def _redact(value: str, secrets: tuple[str, ...]) -> str:
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value

    @staticmethod
    def _lease_token(request: BaseModel) -> str:
        token = getattr(request, "lease_token", "")
        return token if isinstance(token, str) else ""
