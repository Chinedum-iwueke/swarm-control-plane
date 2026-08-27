from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_agent_token
from app.models import (
    Agent,
    AgentCapabilityGrant,
    AgentCharter,
    AgentCredential,
    PackageDeployment,
    RolePackage,
    WorkloadAuthorizationReceipt,
    WorkloadEmergencyGrant,
    WorkloadIdentity,
    WorkloadIdentityControl,
    WorkloadIdentityEvent,
)

POLICY_VERSION = "workload-identity-v1.0.0"
EMERGENCY_SCOPES = {"health:read", "task:halt", "credential:revoke", "workload:isolate"}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def control(db: Session) -> WorkloadIdentityControl:
    row = db.get(WorkloadIdentityControl, 1)
    if row is None:
        policy = {
            "schema_version": POLICY_VERSION,
            "wildcards": False,
            "secret_values_persisted": False,
        }
        row = WorkloadIdentityControl(
            id=1,
            enforcement_active=False,
            policy_version=POLICY_VERSION,
            policy_digest=digest(policy),
        )
        db.add(row)
        db.flush()
    return row


def append_event(
    db: Session, identity: WorkloadIdentity, event_type: str, actor: str, payload: dict
) -> WorkloadIdentityEvent:
    previous = db.scalar(
        select(WorkloadIdentityEvent)
        .where(WorkloadIdentityEvent.identity_id == identity.id)
        .order_by(WorkloadIdentityEvent.sequence.desc())
        .limit(1)
    )
    sequence = 1 if previous is None else previous.sequence + 1
    body = {
        "identity_id": str(identity.id),
        "sequence": sequence,
        "event_type": event_type,
        "actor": actor,
        "payload": payload,
        "prior_event_digest": previous.event_digest if previous else None,
    }
    event = WorkloadIdentityEvent(
        identity_id=identity.id,
        sequence=sequence,
        event_type=event_type,
        actor=actor,
        payload=payload,
        prior_event_digest=body["prior_event_digest"],
        event_digest=digest(body),
    )
    db.add(event)
    return event


def create_identity(db: Session, payload) -> WorkloadIdentity:
    now = datetime.now(UTC)
    agent = db.get(Agent, payload.agent_id)
    charter = db.get(AgentCharter, payload.charter_id)
    package = db.get(RolePackage, payload.package_id)
    deployment = db.scalar(
        select(PackageDeployment).where(
            PackageDeployment.agent_id == payload.agent_id,
            PackageDeployment.package_id == payload.package_id,
            PackageDeployment.is_active.is_(True),
        )
    )
    if (
        not agent
        or not agent.is_enabled
        or not charter
        or charter.agent_id != agent.id
        or charter.status != "active"
        or not package
        or not deployment
    ):
        raise HTTPException(
            status_code=409,
            detail="Identity requires an enabled agent with the exact active charter and package deployment.",
        )
    grants = db.scalars(
        select(AgentCapabilityGrant).where(
            AgentCapabilityGrant.agent_id == agent.id,
            AgentCapabilityGrant.charter_id == charter.id,
            AgentCapabilityGrant.package_id == package.id,
            AgentCapabilityGrant.status == "active",
            AgentCapabilityGrant.expires_at > now,
        )
    ).all()
    if not grants:
        raise HTTPException(
            status_code=409,
            detail="Identity requires active exact-package capability grants.",
        )
    allowed_scopes = scopes_for_package(package.manifest)
    if not set(payload.scopes).issubset(allowed_scopes):
        raise HTTPException(
            status_code=422,
            detail="Requested workload scope exceeds the active package authority.",
        )
    manifest = {
        "schema_version": POLICY_VERSION,
        "agent_id": str(agent.id),
        "charter_digest": charter.manifest_digest,
        "package_digest": package.manifest_digest,
        "machine": agent.machine,
        "audience": payload.audience,
        "scopes": sorted(payload.scopes),
        "accountable_owner": payload.accountable_owner,
        "expires_at": payload.expires_at.isoformat(),
    }
    identity = WorkloadIdentity(
        agent_id=agent.id,
        charter_id=charter.id,
        package_id=package.id,
        version=payload.version,
        machine=agent.machine,
        audience=payload.audience,
        scopes=sorted(payload.scopes),
        accountable_owner=payload.accountable_owner,
        manifest=manifest,
        manifest_digest=digest(manifest),
        status="active",
        valid_from=now,
        expires_at=payload.expires_at,
        created_by=payload.created_by,
    )
    db.add(identity)
    db.flush()
    append_event(
        db,
        identity,
        "created",
        payload.created_by,
        {"manifest_digest": identity.manifest_digest},
    )
    return identity


def scopes_for_package(manifest: dict) -> set[str]:
    scopes = {"identity:read", "heartbeat:write", "control:read", "package:read"}
    task_types = set(manifest.get("task_types", []))
    if task_types:
        scopes |= {"task:lease", "task:execute"}
    if any(item.startswith("infrastructure_") for item in task_types):
        scopes.add("infrastructure:broker")
    if "founder_request" in task_types:
        scopes.add("proposal:write")
    if any(item.startswith("research_") for item in task_types):
        scopes.add("research:write")
    if "fleet_observation" in task_types:
        scopes.add("fleet:write")
    if "operational_memory" in task_types:
        scopes.add("notes:write")
    return scopes


def required_scope(method: str, path: str) -> str:
    if path.endswith("/heartbeat") and path.startswith("/v1/agent/tasks/"):
        return "task:execute"
    if path == "/v1/agent/heartbeat":
        return "heartbeat:write"
    if path in {"/v1/agent/me", "/v1/agent/control"}:
        return "identity:read" if path.endswith("/me") else "control:read"
    if path.startswith("/v1/agent/tasks"):
        if path.endswith("/lease"):
            return "task:lease"
        if path.endswith("/broker-ticket"):
            return "infrastructure:broker"
        return "task:execute"
    if path.startswith("/v1/agent/packages"):
        return "package:read"
    if path.startswith("/v1/agent/proposals"):
        return "proposal:write"
    if path.startswith("/v1/agent/research"):
        return "research:write"
    if path.startswith("/v1/agent/fleet"):
        return "fleet:write"
    if path.startswith("/v1/agent/operational-notes"):
        return "notes:write"
    if path.startswith("/v1/agent/governance"):
        return "governance:read"
    return "identity:read"


def validate_identity(
    db: Session,
    agent: Agent,
    credential: AgentCredential,
    method: str,
    path: str,
    now: datetime,
) -> WorkloadIdentity | None:
    state = control(db)
    if not state.enforcement_active:
        return None
    identity = (
        db.get(WorkloadIdentity, credential.workload_identity_id)
        if credential.workload_identity_id
        else None
    )
    if (
        not identity
        or identity.status != "active"
        or identity.valid_from > now
        or identity.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active workload identity required.",
        )
    if identity.agent_id != agent.id or identity.machine != agent.machine:
        raise HTTPException(
            status_code=403, detail="Workload identity subject or machine mismatch."
        )
    charter = db.get(AgentCharter, identity.charter_id)
    package = db.get(RolePackage, identity.package_id)
    deployment = db.scalar(
        select(PackageDeployment).where(
            PackageDeployment.agent_id == agent.id,
            PackageDeployment.package_id == identity.package_id,
            PackageDeployment.is_active.is_(True),
        )
    )
    if (
        not charter
        or charter.status != "active"
        or charter.agent_id != agent.id
        or not package
        or not deployment
    ):
        raise HTTPException(
            status_code=403,
            detail="Workload identity authority snapshot is no longer active.",
        )
    grants = db.scalars(
        select(AgentCapabilityGrant).where(
            AgentCapabilityGrant.agent_id == agent.id,
            AgentCapabilityGrant.charter_id == charter.id,
            AgentCapabilityGrant.package_id == package.id,
            AgentCapabilityGrant.status == "active",
            AgentCapabilityGrant.machine == agent.machine,
            AgentCapabilityGrant.expires_at > now,
        )
    ).all()
    if not set(package.manifest.get("required_capabilities", [])).issubset(
        {item.capability for item in grants}
    ):
        raise HTTPException(
            status_code=403,
            detail="Workload identity capability grants are incomplete or expired.",
        )
    scope = required_scope(method, path)
    active_scopes = set(identity.scopes)
    emergency = db.scalars(
        select(WorkloadEmergencyGrant).where(
            WorkloadEmergencyGrant.identity_id == identity.id,
            WorkloadEmergencyGrant.status == "active",
            WorkloadEmergencyGrant.starts_at <= now,
            WorkloadEmergencyGrant.expires_at > now,
        )
    ).all()
    active_scopes |= {item for grant in emergency for item in grant.scopes}
    if scope not in active_scopes:
        raise HTTPException(status_code=403, detail=f"Workload scope denied: {scope}.")
    return identity


def bind_credentials(db: Session, identity: WorkloadIdentity, actor: str) -> int:
    credentials = db.scalars(
        select(AgentCredential).where(
            AgentCredential.agent_id == identity.agent_id,
            AgentCredential.revoked_at.is_(None),
        )
    ).all()
    changed = [item for item in credentials if item.workload_identity_id != identity.id]
    for credential in changed:
        credential.workload_identity_id = identity.id
    if changed:
        append_event(
            db,
            identity,
            "credentials_bound",
            actor,
            {"credential_prefixes": sorted(item.token_prefix for item in changed)},
        )
    return len(changed)


def activate_enforcement(db: Session, actor: str) -> dict:
    now = datetime.now(UTC)
    credentials = db.scalars(
        select(AgentCredential)
        .join(Agent, Agent.id == AgentCredential.agent_id)
        .join(PackageDeployment, PackageDeployment.agent_id == Agent.id)
        .where(
            Agent.is_enabled.is_(True),
            PackageDeployment.is_active.is_(True),
            AgentCredential.revoked_at.is_(None),
        )
        .distinct()
    ).all()
    uncovered = [item for item in credentials if item.workload_identity_id is None]
    if uncovered:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot activate: {len(uncovered)} active credentials lack workload identity.",
        )
    state = control(db)
    state.enforcement_active = True
    state.activated_by = actor
    state.activated_at = now
    return {
        "enforcement_active": True,
        "policy_version": state.policy_version,
        "policy_digest": state.policy_digest,
        "covered_credentials": len(credentials),
        "uncovered_credentials": 0,
    }


def authorize(db: Session, payload) -> WorkloadAuthorizationReceipt:
    identity = db.get(WorkloadIdentity, payload.identity_id)
    credential = db.scalar(
        select(AgentCredential).where(
            AgentCredential.token_prefix == payload.credential_prefix,
            AgentCredential.workload_identity_id == payload.identity_id,
        )
    )
    if identity is None:
        raise HTTPException(status_code=404, detail="Workload identity not found.")
    allowed = bool(
        identity
        and credential
        and identity.status == "active"
        and payload.required_scope in identity.scopes
    )
    reason = "scope-authorized" if allowed else "subject-scope-or-credential-mismatch"
    safe_context = {
        key: value
        for key, value in payload.context.items()
        if "secret" not in key.lower()
        and "token" not in key.lower()
        and "password" not in key.lower()
    }
    body = {
        "identity_id": str(payload.identity_id),
        "credential_prefix": payload.credential_prefix,
        "action": payload.action,
        "required_scope": payload.required_scope,
        "allowed": allowed,
        "reason": reason,
        "context": safe_context,
        "nonce": str(datetime.now(UTC).timestamp()),
    }
    receipt = WorkloadAuthorizationReceipt(
        identity_id=payload.identity_id,
        credential_prefix=payload.credential_prefix,
        action=payload.action,
        required_scope=payload.required_scope,
        allowed=allowed,
        reason=reason,
        context=safe_context,
        receipt_digest=digest(body),
    )
    db.add(receipt)
    return receipt


def rotate(
    db: Session, identity: WorkloadIdentity, actor: str, overlap_seconds: int
) -> tuple[AgentCredential, str, AgentCredential]:
    now = datetime.now(UTC)
    prior = db.scalar(
        select(AgentCredential)
        .where(
            AgentCredential.agent_id == identity.agent_id,
            AgentCredential.workload_identity_id == identity.id,
            AgentCredential.revoked_at.is_(None),
        )
        .order_by(AgentCredential.created_at.desc())
        .limit(1)
    )
    if not prior:
        raise HTTPException(
            status_code=409, detail="No active scoped credential to rotate."
        )
    generated = create_agent_token()
    overlap = now + timedelta(seconds=overlap_seconds)
    prior.rotation_state = "overlap"
    prior.overlap_expires_at = overlap
    new = AgentCredential(
        agent_id=identity.agent_id,
        workload_identity_id=identity.id,
        rotation_parent_id=prior.id,
        rotation_state="active",
        token_prefix=generated.prefix,
        token_digest=generated.digest,
        expires_at=min(identity.expires_at, now + timedelta(days=90)),
    )
    db.add(new)
    db.flush()
    append_event(
        db,
        identity,
        "credential_rotated",
        actor,
        {
            "prior_prefix": prior.token_prefix,
            "new_prefix": new.token_prefix,
            "overlap_expires_at": overlap.isoformat(),
        },
    )
    return new, generated.token, prior


def finalize_rotation(
    db: Session, identity: WorkloadIdentity, actor: str, rollback: bool = False
) -> None:
    newest = db.scalar(
        select(AgentCredential)
        .where(
            AgentCredential.workload_identity_id == identity.id,
            AgentCredential.rotation_parent_id.is_not(None),
            AgentCredential.revoked_at.is_(None),
        )
        .order_by(AgentCredential.created_at.desc())
        .limit(1)
    )
    if not newest:
        raise HTTPException(status_code=409, detail="No pending rotation.")
    prior = db.get(AgentCredential, newest.rotation_parent_id)
    now = datetime.now(UTC)
    if rollback:
        if prior.overlap_expires_at is None or prior.overlap_expires_at <= now:
            raise HTTPException(
                status_code=409, detail="Credential rollback window has expired."
            )
        newest.revoked_at = now
        newest.rotation_state = "rolled_back"
        prior.rotation_state = "active"
        prior.overlap_expires_at = None
        event = "credential_rotation_rolled_back"
    else:
        prior.revoked_at = now
        prior.rotation_state = "revoked"
        prior.overlap_expires_at = None
        event = "credential_rotation_finalized"
    append_event(
        db,
        identity,
        event,
        actor,
        {"prior_prefix": prior.token_prefix, "new_prefix": newest.token_prefix},
    )
