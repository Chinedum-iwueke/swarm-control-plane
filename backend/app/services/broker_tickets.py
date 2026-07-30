import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, Task, TaskApproval
from app.schemas.infrastructure import (
    BrokerTicketPayload,
    BrokerTicketResponse,
    InfrastructureContract,
)


def canonical_ticket(payload: BrokerTicketPayload) -> bytes:
    return json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def issue_broker_ticket(
    db: Session,
    task: Task,
    agent: Agent,
    *,
    secret: str,
    now: datetime | None = None,
) -> BrokerTicketResponse:
    issued_at = now or datetime.now(UTC)
    if task.task_type not in {
        "infrastructure_observation",
        "infrastructure_operation",
    }:
        raise HTTPException(status_code=422, detail="Task type cannot use the broker.")
    try:
        contract = InfrastructureContract.model_validate(task.input_contract)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Infrastructure contract is invalid."
        ) from exc
    if task.risk_level > 3:
        raise HTTPException(status_code=422, detail="Broker risk ceiling exceeded.")
    observations = {
        "observe-control-plane",
        "preflight-invariance-postgres",
        "verify-invariance-postgres",
        "prepare-invariance-cutover",
    }
    risk_two = {"stage-invariance-postgres"}
    if contract.operation in observations and task.risk_level != 0:
        raise HTTPException(status_code=422, detail="Observation must use risk zero.")
    if contract.operation in risk_two and task.risk_level != 2:
        raise HTTPException(status_code=422, detail="Operation must use risk two.")
    if (
        contract.operation not in observations | risk_two
        and task.risk_level != 3
    ):
        raise HTTPException(status_code=422, detail="Operation must use risk three.")
    if task.risk_level >= 2:
        approval = db.scalar(
            select(TaskApproval).where(TaskApproval.task_id == task.id)
        )
        if (
            approval is None
            or approval.status != "consumed"
            or approval.plan_digest != task.plan_digest
            or approval.consumed_at is None
            or approval.expires_at is None
            or approval.expires_at <= issued_at
        ):
            raise HTTPException(
                status_code=409,
                detail="A consumed approval for this exact plan is required.",
            )
    if task.lease_expires_at is None or task.lease_expires_at <= issued_at:
        raise HTTPException(status_code=409, detail="Task lease has expired.")
    nonce = hashlib.sha256(
        f"{task.id}:{task.attempt_count}:{task.plan_digest}".encode()
    ).hexdigest()
    payload = BrokerTicketPayload(
        schema_version=1,
        task_id=task.id,
        task_number=task.task_number,
        attempt_number=task.attempt_count,
        agent_id=agent.id,
        machine=agent.machine,
        task_type=task.task_type,
        risk_level=task.risk_level,
        plan_digest=task.plan_digest,
        contract=contract,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=min(task.lease_expires_at, issued_at + timedelta(seconds=60)),
    )
    signature = hmac.new(secret.encode(), canonical_ticket(payload), hashlib.sha256)
    return BrokerTicketResponse(payload=payload, signature=signature.hexdigest())
