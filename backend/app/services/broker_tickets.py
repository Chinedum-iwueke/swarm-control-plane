import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    RunbookPackage,
    RunbookPromotion,
    Task,
    TaskApproval,
)
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
    if task.risk_level > 5:
        raise HTTPException(status_code=422, detail="Broker risk ceiling exceeded.")
    if contract.runbook == "vm2-platform-operations":
        _validate_packaged_operation(db, contract, task, issued_at)
    observations = {
        "observe-control-plane",
        "preflight-invariance-postgres",
        "verify-invariance-postgres",
        "prepare-invariance-cutover",
    }
    risk_two = {"stage-invariance-postgres"}
    packaged = contract.runbook == "vm2-platform-operations"
    if contract.operation in observations and task.risk_level not in (
        {0, 1} if packaged else {0}
    ):
        raise HTTPException(status_code=422, detail="Observation must use risk zero.")
    if contract.operation in risk_two and task.risk_level != 2:
        raise HTTPException(status_code=422, detail="Operation must use risk two.")
    if (
        contract.operation not in observations | risk_two
        and not packaged
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


def _validate_packaged_operation(
    db: Session,
    contract: InfrastructureContract,
    task: Task,
    issued_at: datetime,
) -> None:
    package = db.scalar(
        select(RunbookPackage).where(
            RunbookPackage.name == contract.package_name,
            RunbookPackage.version == contract.package_version,
            RunbookPackage.manifest_digest == contract.package_digest,
        )
    )
    if package is None:
        raise HTTPException(status_code=409, detail="Runbook package is not registered.")
    promotion = db.scalar(
        select(RunbookPromotion)
        .where(RunbookPromotion.package_id == package.id)
        .order_by(RunbookPromotion.recorded_at.desc(), RunbookPromotion.id.desc())
    )
    if promotion is None or promotion.state not in {"approved", "deployed"}:
        raise HTTPException(status_code=409, detail="Runbook package is not approved.")
    rehearsal = db.scalar(
        select(RunbookPromotion).where(
            RunbookPromotion.package_id == package.id,
            RunbookPromotion.state == "rehearsed",
        )
    )
    max_age = package.manifest.get("rehearsal", {}).get("max_evidence_age_hours")
    if (
        rehearsal is None
        or not isinstance(max_age, int)
        or rehearsal.recorded_at + timedelta(hours=max_age) <= issued_at
    ):
        raise HTTPException(status_code=409, detail="Runbook rehearsal is stale.")
    operations = {
        item["name"]: item for item in package.manifest.get("operations", [])
    }
    operation = operations.get(contract.operation)
    if operation is None:
        raise HTTPException(status_code=422, detail="Operation is not in the package.")
    if (
        operation.get("target_profile") != contract.target
        or operation.get("task_type") != task.task_type
        or operation.get("risk_level") != task.risk_level
    ):
        raise HTTPException(status_code=422, detail="Task does not match package policy.")
    _validate_packaged_parameters(operation.get("parameters", {}), contract.parameters)


def _validate_packaged_parameters(definitions: dict, supplied: dict) -> None:
    if set(supplied) - set(definitions):
        raise HTTPException(status_code=422, detail="Unknown operation parameter.")
    if any(
        definition.get("required", True) and name not in supplied
        for name, definition in definitions.items()
    ):
        raise HTTPException(status_code=422, detail="Required operation parameter missing.")
    for name, value in supplied.items():
        definition = definitions[name]
        kind = definition.get("type")
        if kind == "string":
            if not isinstance(value, str) or not value or any(
                character in value for character in "\n\r;&|`$<>"
            ):
                raise HTTPException(status_code=422, detail="Unsafe string parameter.")
            allowed = definition.get("allowed_values", [])
            if allowed and value not in allowed:
                raise HTTPException(status_code=422, detail="Parameter is not allowlisted.")
        elif kind == "boolean" and not isinstance(value, bool):
            raise HTTPException(status_code=422, detail="Boolean parameter required.")
        elif kind == "integer" and (
            isinstance(value, bool) or not isinstance(value, int)
        ):
            raise HTTPException(status_code=422, detail="Integer parameter required.")
        elif kind == "integer" and (
            (definition.get("minimum") is not None and value < definition["minimum"])
            or (
                definition.get("maximum") is not None
                and value > definition["maximum"]
            )
        ):
            raise HTTPException(status_code=422, detail="Integer parameter out of range.")
        elif kind == "cidr-list":
            import ipaddress

            try:
                networks = [ipaddress.ip_network(item, strict=True) for item in value]
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail="Invalid CIDR parameter.") from exc
            if not networks or any(
                network.prefixlen < (8 if network.version == 4 else 32)
                for network in networks
            ):
                raise HTTPException(status_code=422, detail="CIDR parameter is too broad.")
        elif kind not in {"string", "integer", "boolean", "cidr-list"}:
            raise HTTPException(status_code=422, detail="Unknown parameter type.")
