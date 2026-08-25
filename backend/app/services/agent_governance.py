import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    AgentCapabilityGrant,
    AgentCharter,
    AgentGrantEvent,
    PackageDeployment,
    RolePackage,
)
from app.schemas.agent_governance import (
    AgentCapabilityGrantCreate,
    AgentCharterCreate,
    EffectiveAuthorityRequest,
)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def create_charter(db: Session, payload: AgentCharterCreate) -> AgentCharter:
    agent = db.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found.")
    manifest = payload.manifest.model_dump(mode="json")
    if digest(manifest) != payload.manifest_digest:
        raise HTTPException(422, "Charter manifest digest mismatch.")
    if agent.machine not in manifest["allowed_machines"]:
        raise HTTPException(422, "Charter does not allow the registered machine.")
    if not set(manifest["capabilities"]).issubset(agent.capabilities):
        raise HTTPException(422, "Charter exceeds registered agent capabilities.")
    if manifest["risk_ceiling"] > agent.risk_ceiling:
        raise HTTPException(422, "Charter exceeds registered agent risk ceiling.")
    charter = AgentCharter(agent_id=payload.agent_id, version=payload.version, manifest=manifest,
                           manifest_digest=payload.manifest_digest, created_by=payload.created_by)
    db.add(charter)
    db.commit(); db.refresh(charter)
    return charter


def activate_charter(db: Session, charter: AgentCharter, actor: str) -> AgentCharter:
    if charter.status == "active":
        return charter
    if charter.status != "draft":
        raise HTTPException(409, "Only a draft charter can be activated.")
    now = datetime.now(UTC)
    previous = db.scalar(select(AgentCharter).where(AgentCharter.agent_id == charter.agent_id, AgentCharter.status == "active"))
    if previous:
        previous.status = "superseded"
        charter.supersedes_id = previous.id
        for grant in db.scalars(select(AgentCapabilityGrant).where(AgentCapabilityGrant.charter_id == previous.id, AgentCapabilityGrant.status == "active")):
            revoke_grant(db, grant, actor, "charter superseded", commit=False)
    charter.status = "active"; charter.activated_by = actor; charter.activated_at = now
    db.commit(); db.refresh(charter)
    return charter


def create_grant(db: Session, payload: AgentCapabilityGrantCreate) -> AgentCapabilityGrant:
    now = datetime.now(UTC)
    charter = db.get(AgentCharter, payload.charter_id)
    agent = db.get(Agent, payload.agent_id)
    if not charter or not agent or charter.agent_id != payload.agent_id or charter.status != "active":
        raise HTTPException(409, "An active charter for this agent is required.")
    if payload.expires_at <= now:
        raise HTTPException(422, "Grant expiry must be in the future.")
    manifest = charter.manifest
    checks = [
        (payload.capability in manifest["capabilities"], "Capability is outside the charter."),
        (payload.machine == agent.machine and payload.machine in manifest["allowed_machines"], "Machine is outside the charter."),
        (set(payload.task_types).issubset(manifest["allowed_task_types"]), "Task type is outside the charter."),
        (set(payload.repositories).issubset(manifest["allowed_repositories"]), "Repository is outside the charter."),
        (payload.risk_ceiling <= manifest["risk_ceiling"], "Risk exceeds the charter."),
        (payload.accountable_owner == manifest["accountable_owner"], "Accountable owner differs from the charter."),
        (payload.capability not in manifest.get("conflicts", []), "Capability has a declared conflict."),
        (payload.capability not in manifest.get("forbidden_actions", []), "Capability is prohibited by the charter."),
    ]
    for valid, message in checks:
        if not valid: raise HTTPException(422, message)
    package = _active_package(db, agent.id)
    if package is None:
        raise HTTPException(409, "An active role-package deployment is required.")
    pm = package.manifest
    if payload.capability not in pm["required_capabilities"] or not set(payload.task_types).issubset(pm["task_types"]):
        raise HTTPException(422, "Grant exceeds the active role package.")
    record = payload.model_dump(mode="json")
    grant = AgentCapabilityGrant(**payload.model_dump(), record_digest=digest(record))
    db.add(grant); db.flush(); _event(db, grant, "granted", payload.granted_by, record)
    db.commit(); db.refresh(grant)
    return grant


def revoke_grant(db: Session, grant: AgentCapabilityGrant, actor: str, reason: str, *, commit: bool = True) -> AgentCapabilityGrant:
    if grant.status != "active":
        return grant
    grant.status = "revoked"; grant.revoked_by = actor; grant.revoked_at = datetime.now(UTC); grant.revocation_reason = reason
    _event(db, grant, "revoked", actor, {"reason": reason})
    if commit: db.commit(); db.refresh(grant)
    return grant


def resolve(db: Session, agent_id: UUID, request: EffectiveAuthorityRequest, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC); reasons: list[str] = []
    agent = db.get(Agent, agent_id)
    charter = db.scalar(select(AgentCharter).where(AgentCharter.agent_id == agent_id, AgentCharter.status == "active"))
    package = _active_package(db, agent_id)
    grant = db.scalar(select(AgentCapabilityGrant).where(AgentCapabilityGrant.agent_id == agent_id,
        AgentCapabilityGrant.capability == request.capability, AgentCapabilityGrant.status == "active").order_by(AgentCapabilityGrant.created_at.desc()))
    if not agent or not agent.is_enabled: reasons.append("agent-disabled-or-missing")
    if not charter: reasons.append("active-charter-missing")
    if not package: reasons.append("active-package-missing")
    if not grant: reasons.append("active-grant-missing")
    if agent and (agent.machine != request.machine or request.capability not in agent.capabilities or request.risk_level > agent.risk_ceiling): reasons.append("agent-registration-mismatch")
    if charter:
        m = charter.manifest
        if request.capability not in m["capabilities"] or request.machine not in m["allowed_machines"] or request.task_type not in m["allowed_task_types"] or request.risk_level > m["risk_ceiling"] or (request.repository and request.repository not in m["allowed_repositories"]): reasons.append("charter-boundary-violation")
        if request.capability in m.get("conflicts", []) or request.capability in m.get("forbidden_actions", []): reasons.append("charter-conflict-or-prohibition")
    if package:
        m = package.manifest
        if request.capability not in m["required_capabilities"] or request.machine not in m["allowed_machines"] or request.task_type not in m["task_types"] or request.risk_level > m["risk_ceiling"] or (request.repository and request.repository not in m["repository_profile"]["repositories"]): reasons.append("package-boundary-violation")
    if grant:
        if grant.expires_at <= now: reasons.append("grant-expired")
        if request.machine != grant.machine or request.task_type not in grant.task_types or request.risk_level > grant.risk_ceiling or (request.repository and request.repository not in grant.repositories): reasons.append("grant-boundary-violation")
    result = {"agent_id": agent_id, "allowed": not reasons, "reasons": sorted(set(reasons)),
              "accountable_owner": grant.accountable_owner if grant else None,
              "charter_digest": charter.manifest_digest if charter else None,
              "package_digest": package.manifest_digest if package else None,
              "grant_digest": grant.record_digest if grant else None, "resolved_at": now}
    result["snapshot_digest"] = digest(result)
    return result


def _active_package(db: Session, agent_id: UUID) -> RolePackage | None:
    return db.scalar(select(RolePackage).join(PackageDeployment, PackageDeployment.package_id == RolePackage.id).where(PackageDeployment.agent_id == agent_id, PackageDeployment.is_active.is_(True)).order_by(PackageDeployment.deployed_at.desc()))


def _event(db: Session, grant: AgentCapabilityGrant, event_type: str, actor: str, payload: dict) -> None:
    previous = db.scalar(select(AgentGrantEvent).where(AgentGrantEvent.grant_id == grant.id).order_by(AgentGrantEvent.sequence.desc()))
    sequence = (previous.sequence + 1) if previous else 1
    body = {"grant_id": str(grant.id), "sequence": sequence, "event_type": event_type, "actor": actor, "payload": payload, "prior_event_digest": previous.event_digest if previous else None}
    db.add(AgentGrantEvent(grant_id=grant.id, sequence=sequence, event_type=event_type, actor=actor, payload=payload, prior_event_digest=body["prior_event_digest"], event_digest=digest(body)))
