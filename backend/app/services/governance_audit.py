from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authority import (
    AuthorityDecisionRecord,
    AuthorityDelegation,
    AuthorityException,
    AuthorityPolicySnapshot,
)
from app.models.control import ControlEvent
from app.models.governance import ApprovalEvent, TaskApproval
from app.models.governance_audit import GovernanceAuditExport
from app.models.institutional_lifecycle import (
    InstitutionalLifecycleEvent,
    InstitutionalLifecycleProjection,
)
from app.models.lifecycle_consequence import LifecycleConsequence
from app.models.operation import Operation, OperationEvent
from app.models.proposal import FounderProposal
from app.models.task import Task
from app.models.task_event import TaskEvent

SCHEMA_VERSION = "governance-audit-export-v1.0.0"
GENESIS = "0" * 64
SENSITIVE_KEYS = (
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "api_key",
    "signing_key",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=_json_default
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def create_export(
    db: Session, requested_by: str, signing_secret: str
) -> GovernanceAuditExport:
    events = _collect_events(db)
    chained = []
    prior = GENESIS
    for sequence, event in enumerate(events, start=1):
        item = {"sequence": sequence, "prior_export_digest": prior, **event}
        item["record_digest"] = digest(item)
        prior = item["record_digest"]
        chained.append(item)

    policy_digests = sorted(
        {
            event["policy"]["digest"]
            for event in chained
            if event.get("policy", {}).get("digest")
        }
    )
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "requested_by": requested_by,
        "event_count": len(chained),
        "policy_digests": policy_digests,
        "genesis_digest": GENESIS,
        "terminal_digest": prior,
        "events": chained,
        "claim_boundary": (
            "Governance reconstruction only; this export grants no execution, "
            "deployment, secret, capital, or order authority."
        ),
    }
    bundle_digest = digest(unsigned)
    private_key = _private_key(signing_secret)
    public_key = (
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    )
    key_id = hashlib.sha256(bytes.fromhex(public_key)).hexdigest()
    signature = private_key.sign(bytes.fromhex(bundle_digest)).hex()
    bundle = {
        **unsigned,
        "bundle_digest": bundle_digest,
        "signature": {
            "algorithm": "ed25519",
            "key_id": key_id,
            "public_key": public_key,
            "value": signature,
        },
    }
    record = GovernanceAuditExport(
        id=uuid4(),
        schema_version=SCHEMA_VERSION,
        requested_by=requested_by,
        event_count=len(chained),
        bundle_digest=bundle_digest,
        signature=signature,
        public_key=public_key,
        key_id=key_id,
        bundle=bundle,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def verify_bundle(bundle: dict) -> dict:
    try:
        if bundle["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema version")
        events = bundle["events"]
        if bundle["event_count"] != len(events):
            raise ValueError("event count mismatch")
        prior = bundle["genesis_digest"]
        if prior != GENESIS:
            raise ValueError("invalid genesis digest")
        projections: dict[str, dict] = {}
        for expected_sequence, event in enumerate(events, start=1):
            if event["sequence"] != expected_sequence:
                raise ValueError("event sequence is not contiguous")
            if event["prior_export_digest"] != prior:
                raise ValueError("event chain is broken")
            claimed = event["record_digest"]
            content = {
                key: value for key, value in event.items() if key != "record_digest"
            }
            if digest(content) != claimed:
                raise ValueError("event digest mismatch")
            prior = claimed
            _reconstruct(projections, event)
        _validate_references(events)
        if bundle["terminal_digest"] != prior:
            raise ValueError("terminal digest mismatch")
        signature = bundle["signature"]
        if signature["algorithm"] != "ed25519":
            raise ValueError("unsupported signature algorithm")
        public = bytes.fromhex(signature["public_key"])
        key_id = hashlib.sha256(public).hexdigest()
        if signature["key_id"] != key_id:
            raise ValueError("signature key identity mismatch")
        unsigned = {
            key: value
            for key, value in bundle.items()
            if key not in {"bundle_digest", "signature"}
        }
        bundle_digest = digest(unsigned)
        if bundle["bundle_digest"] != bundle_digest:
            raise ValueError("bundle digest mismatch")
        Ed25519PublicKey.from_public_bytes(public).verify(
            bytes.fromhex(signature["value"]), bytes.fromhex(bundle_digest)
        )
    except (KeyError, TypeError, ValueError, InvalidSignature) as error:
        raise HTTPException(
            status_code=422, detail=f"Invalid audit export: {error}"
        ) from None
    return {
        "valid": True,
        "event_count": len(events),
        "bundle_digest": bundle_digest,
        "key_id": key_id,
        "reconstructed": projections,
    }


def _collect_events(db: Session) -> list[dict]:
    policies = {
        item.id: item for item in db.scalars(select(AuthorityPolicySnapshot)).all()
    }
    decisions = {
        item.id: item for item in db.scalars(select(AuthorityDecisionRecord)).all()
    }
    projections = {
        item.id: item
        for item in db.scalars(select(InstitutionalLifecycleProjection)).all()
    }
    lifecycle_events = {
        item.id: item for item in db.scalars(select(InstitutionalLifecycleEvent)).all()
    }
    tasks = {item.id: item for item in db.scalars(select(Task)).all()}
    approvals = {item.id: item for item in db.scalars(select(TaskApproval)).all()}
    operations = {item.id: item for item in db.scalars(select(Operation)).all()}
    rows: list[dict] = []
    for policy in policies.values():
        rows.append(
            _event(
                "authority-policy",
                policy.id,
                policy.created_at,
                policy.created_by,
                "activate" if policy.status == "active" else "register",
                "authority-policy",
                f"{policy.policy_key}:{policy.version}",
                policy.manifest_digest,
                policy,
                [],
                {
                    "status": policy.status,
                    "manifest": policy.manifest,
                    "effective_from": policy.effective_from,
                    "effective_until": policy.effective_until,
                    "supersedes_id": policy.supersedes_id,
                },
            )
        )
    for task in tasks.values():
        rows.append(
            _event(
                "task",
                task.id,
                task.created_at,
                task.created_by,
                "create",
                "task",
                task.task_number,
                task.plan_digest,
                None,
                [],
                {
                    "task_id": task.id,
                    "project": task.project,
                    "task_type": task.task_type,
                    "title": task.title,
                    "objective": task.objective,
                    "status": task.status,
                    "risk_level": task.risk_level,
                    "input_contract": task.input_contract,
                    "expected_outputs": task.expected_outputs,
                    "acceptance_criteria": task.acceptance_criteria,
                    "approval_policy": task.approval_policy,
                    "approval_required": task.approval_required,
                    "required_capabilities": task.required_capabilities,
                    "allowed_machines": task.allowed_machines,
                    "parent_task_id": task.parent_task_id,
                    "mission_id": task.mission_id,
                },
            )
        )
    for task_event in db.scalars(select(TaskEvent)).all():
        task = tasks.get(task_event.task_id)
        rows.append(
            _event(
                "task-event",
                task_event.id,
                task_event.created_at,
                str(task_event.agent_id) if task_event.agent_id else "control-plane",
                task_event.event_type,
                "task",
                task.task_number if task else str(task_event.task_id),
                task.plan_digest if task else None,
                None,
                [],
                {
                    "task_id": task_event.task_id,
                    "attempt_number": task_event.attempt_number,
                    "message": task_event.message,
                    "payload": task_event.payload,
                },
            )
        )
    for approval in approvals.values():
        task = tasks.get(approval.task_id)
        rows.append(
            _event(
                "task-approval",
                approval.id,
                approval.created_at,
                approval.requested_by,
                "request-approval",
                "task",
                task.task_number if task else str(approval.task_id),
                approval.plan_digest,
                None,
                [],
                {
                    "task_id": approval.task_id,
                    "status": approval.status,
                    "risk_level": approval.risk_level,
                    "scope": approval.scope,
                    "decided_by": approval.decided_by,
                    "decision_reason": approval.decision_reason,
                    "issued_at": approval.issued_at,
                    "expires_at": approval.expires_at,
                    "consumed_at": approval.consumed_at,
                },
            )
        )
    for approval_event in db.scalars(select(ApprovalEvent)).all():
        approval = approvals.get(approval_event.approval_id)
        task = tasks.get(approval.task_id) if approval else None
        rows.append(
            _event(
                "approval-event",
                approval_event.id,
                approval_event.created_at,
                approval_event.actor,
                approval_event.event_type,
                "task-approval",
                str(approval_event.approval_id),
                approval.plan_digest if approval else None,
                None,
                [],
                {
                    "approval_id": approval_event.approval_id,
                    "task_id": task.id if task else None,
                    "reason": approval_event.reason,
                    "payload": approval_event.payload,
                },
            )
        )
    for proposal in db.scalars(select(FounderProposal)).all():
        rows.append(
            _event(
                "founder-proposal",
                proposal.id,
                proposal.created_at,
                proposal.decided_by or "founder-planner",
                proposal.status,
                "founder-proposal",
                str(proposal.id),
                proposal.proposal_digest,
                None,
                [],
                {
                    "source_task_id": proposal.source_task_id,
                    "materialized_task_id": proposal.materialized_task_id,
                    "conversation_id": proposal.conversation_id,
                    "conversation_revision": proposal.conversation_revision,
                    "planner_agent_id": proposal.planner_agent_id,
                    "proposal": proposal.proposal,
                    "decision_reason": proposal.decision_reason,
                    "decided_at": proposal.decided_at,
                },
            )
        )
    for control in db.scalars(select(ControlEvent)).all():
        rows.append(
            _event(
                "control-event",
                control.id,
                control.created_at,
                control.actor,
                control.event_type,
                "control-scope",
                f"{control.scope_type}:{control.scope_key}",
                digest(
                    {"scope_type": control.scope_type, "scope_key": control.scope_key}
                ),
                None,
                [],
                {"reason": control.reason, "payload": control.payload},
            )
        )
    for operation in operations.values():
        rows.append(
            _event(
                "operation",
                operation.id,
                operation.created_at,
                operation.owner_id or operation.owner_type,
                "register",
                "operation",
                operation.operation_key,
                operation.input_digest or operation.record_digest,
                None,
                [],
                {
                    "kind": operation.kind,
                    "title": operation.title,
                    "project": operation.project,
                    "machine": operation.machine,
                    "state": operation.state,
                    "phase": operation.phase,
                    "record_digest": operation.record_digest,
                },
            )
        )
    for operation_event in db.scalars(select(OperationEvent)).all():
        operation = operations.get(operation_event.operation_id)
        rows.append(
            _event(
                "operation-event",
                operation_event.id,
                operation_event.created_at,
                operation_event.actor,
                operation_event.event_type,
                "operation",
                operation.operation_key
                if operation
                else str(operation_event.operation_id),
                operation.input_digest if operation else None,
                None,
                [],
                {
                    "operation_id": operation_event.operation_id,
                    "sequence": operation_event.sequence,
                    "state": operation_event.state,
                    "phase": operation_event.phase,
                    "detail": operation_event.detail,
                    "source_record_digest": operation_event.record_digest,
                },
            )
        )
    for delegation in db.scalars(select(AuthorityDelegation)).all():
        rows.append(
            _event(
                "authority-delegation",
                delegation.id,
                delegation.created_at,
                delegation.grantor_actor,
                "delegate",
                "authority-delegation",
                str(delegation.id),
                None,
                policies.get(delegation.policy_id),
                [],
                {
                    "grantee_actor": delegation.grantee_actor,
                    "decision_types": delegation.decision_types,
                    "scope": delegation.scope,
                    "max_risk": delegation.max_risk,
                    "environment": delegation.environment,
                    "status": delegation.status,
                    "expires_at": delegation.expires_at,
                    "revoked_at": delegation.revoked_at,
                    "reason": delegation.reason,
                },
            )
        )
    for exception in db.scalars(select(AuthorityException)).all():
        rows.append(
            _event(
                "authority-exception",
                exception.id,
                exception.created_at,
                exception.requester,
                "request-exception",
                "authority-exception",
                str(exception.id),
                exception.record_digest,
                policies.get(exception.policy_id),
                [],
                {
                    "rule_key": exception.rule_key,
                    "approver": exception.approver,
                    "independent_reviewer": exception.independent_reviewer,
                    "scope": exception.scope,
                    "risk_level": exception.risk_level,
                    "compensating_controls": exception.compensating_controls,
                    "status": exception.status,
                    "expires_at": exception.expires_at,
                    "terminal_disposition": exception.terminal_disposition,
                    "reason": exception.reason,
                },
            )
        )
    for decision in decisions.values():
        rows.append(
            _event(
                "authority-decision",
                decision.id,
                decision.created_at,
                decision.actor,
                decision.action,
                decision.object_type,
                decision.object_id,
                decision.object_digest,
                policies.get(decision.policy_id),
                _evidence_list(decision.evidence),
                {
                    "decision_type": decision.decision_type,
                    "effective_roles": decision.effective_roles,
                    "scope": decision.scope,
                    "risk_level": decision.risk_level,
                    "outcome": decision.outcome,
                    "reason": decision.reason,
                    "delegation_id": decision.delegation_id,
                    "exception_id": decision.exception_id,
                    "source_record_digest": decision.record_digest,
                },
            )
        )
    for event in lifecycle_events.values():
        projection = projections[event.projection_id]
        decision = decisions.get(event.authority_decision_id)
        rows.append(
            _event(
                "lifecycle-transition",
                event.id,
                event.created_at,
                event.actor,
                event.command,
                projection.subject_type,
                projection.subject_id,
                projection.subject_digest,
                policies.get(decision.policy_id) if decision else None,
                event.evidence,
                {
                    "dimension": event.dimension,
                    "prior_state": event.prior_state,
                    "resulting_state": event.resulting_state,
                    "expected_version": event.expected_version,
                    "resulting_version": event.resulting_version,
                    "authority_decision_id": event.authority_decision_id,
                    "prior_event_digest": event.prior_event_digest,
                    "source_record_digest": event.record_digest,
                    "effective_at": event.effective_at,
                },
            )
        )
    for consequence in db.scalars(select(LifecycleConsequence)).all():
        source = lifecycle_events[consequence.event_id]
        projection = projections[source.projection_id]
        decision = decisions.get(source.authority_decision_id)
        rows.append(
            _event(
                "lifecycle-consequence",
                consequence.id,
                consequence.created_at,
                source.actor,
                consequence.action,
                projection.subject_type,
                projection.subject_id,
                projection.subject_digest,
                policies.get(decision.policy_id) if decision else None,
                source.evidence,
                {
                    "status": consequence.status,
                    "dimension": source.dimension,
                    "prior_state": consequence.prior_state,
                    "resulting_state": consequence.resulting_state,
                    "rollback_state": consequence.rollback_state,
                    "approvers": consequence.approvers,
                    "affected_descendants": consequence.affected_descendants,
                    "evidence_epoch": consequence.evidence_epoch,
                    "expires_at": consequence.expires_at,
                    "source_event_id": consequence.event_id,
                    "reversed_by_id": consequence.reversed_by_id,
                    "reversal_of_id": consequence.reversal_of_id,
                    "reason": consequence.reason,
                    "source_record_digest": consequence.record_digest,
                },
            )
        )
    return sorted(
        rows, key=lambda item: (item["occurred_at"], item["stream"], item["source_id"])
    )


def _event(
    stream,
    source_id,
    occurred_at,
    actor,
    action,
    object_type,
    object_id,
    object_digest,
    policy,
    evidence,
    payload,
):
    redacted_payload, redactions = _redact(payload)
    return {
        "stream": stream,
        "source_id": str(source_id),
        "occurred_at": _json_default(occurred_at),
        "actor": actor,
        "action": action,
        "object": {"type": object_type, "id": str(object_id), "digest": object_digest},
        "policy": (
            {
                "id": str(policy.id),
                "key": policy.policy_key,
                "version": policy.version,
                "digest": policy.manifest_digest,
            }
            if policy
            else {"id": None, "key": None, "version": None, "digest": None}
        ),
        "evidence": sorted(str(item) for item in evidence),
        "payload": redacted_payload,
        "redactions": redactions,
    }


def _redact(value: Any, path: str = "payload") -> tuple[Any, list[dict]]:
    receipts = []
    if isinstance(value, dict):
        result = {}
        for key in sorted(value):
            child_path = f"{path}.{key}"
            if any(marker in key.lower() for marker in SENSITIVE_KEYS):
                receipt = {"path": child_path, "value_digest": digest(value[key])}
                receipts.append(receipt)
                result[key] = {
                    "redacted": True,
                    "value_digest": receipt["value_digest"],
                }
            else:
                result[key], child = _redact(value[key], child_path)
                receipts.extend(child)
        return result, receipts
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            cleaned, child = _redact(item, f"{path}[{index}]")
            result.append(cleaned)
            receipts.extend(child)
        return result, receipts
    return _json_default(value), receipts


def _reconstruct(projections: dict[str, dict], event: dict) -> None:
    if event["stream"] != "lifecycle-transition":
        return
    key = f"{event['object']['type']}:{event['object']['id']}:{event['payload']['dimension']}"
    expected = event["payload"]["expected_version"]
    current = projections.get(key)
    if current is None and expected != 0:
        raise ValueError("lifecycle history starts after version zero")
    if current is not None and (
        current["version"] != expected
        or current["state"] != event["payload"]["prior_state"]
    ):
        raise ValueError("lifecycle history cannot be reconstructed")
    projections[key] = {
        "state": event["payload"]["resulting_state"],
        "version": event["payload"]["resulting_version"],
        "event_digest": event["payload"]["source_record_digest"],
    }


def _validate_references(events: list[dict]) -> None:
    identities = {(event["stream"], event["source_id"]) for event in events}
    if len(identities) != len(events):
        raise ValueError("duplicate source identity")
    for event in events:
        policy_id = event["policy"]["id"]
        if policy_id and ("authority-policy", policy_id) not in identities:
            raise ValueError("referenced authority policy is missing")
        if event["stream"] == "lifecycle-transition":
            decision = event["payload"].get("authority_decision_id")
            if (
                decision
                and (
                    "authority-decision",
                    str(decision),
                )
                not in identities
            ):
                raise ValueError("referenced authority decision is missing")
        if event["stream"] == "task-event":
            task_id = str(event["payload"]["task_id"])
            if ("task", task_id) not in identities:
                raise ValueError("referenced task is missing")
        if event["stream"] == "task-approval":
            task_id = str(event["payload"]["task_id"])
            if ("task", task_id) not in identities:
                raise ValueError("approved task is missing")
        if event["stream"] == "approval-event":
            approval_id = str(event["payload"]["approval_id"])
            if ("task-approval", approval_id) not in identities:
                raise ValueError("referenced approval is missing")
        if event["stream"] == "founder-proposal":
            source_task_id = str(event["payload"]["source_task_id"])
            if ("task", source_task_id) not in identities:
                raise ValueError("proposal source task is missing")
        if event["stream"] == "operation-event":
            operation_id = str(event["payload"]["operation_id"])
            if ("operation", operation_id) not in identities:
                raise ValueError("referenced operation is missing")
        if event["stream"] == "lifecycle-consequence":
            source = event["payload"].get("source_event_id")
            if source and ("lifecycle-transition", str(source)) not in identities:
                raise ValueError("referenced lifecycle event is missing")
            for field in ("reversed_by_id", "reversal_of_id"):
                reference = event["payload"][field]
                if (
                    reference
                    and (
                        "lifecycle-consequence",
                        str(reference),
                    )
                    not in identities
                ):
                    raise ValueError("referenced lifecycle consequence is missing")


def _private_key(secret: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(secret.encode()).digest()
    )


def _evidence_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [digest(value)] if value else []
    return []


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value
