from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.authority import (
    AuthorityDelegation,
    AuthorityException,
    AuthorityPolicySnapshot,
)
from app.schemas.authority import (
    AuthorityPolicyActivation,
    AuthorityPolicyCreate,
    AuthorityPolicyManifest,
    AuthorityResolutionRequest,
    DelegationCreate,
    ExceptionCreate,
    ExceptionDecision,
)
from app.services.authority import (
    activate_policy,
    active_policy,
    canonical_digest,
    expire_authority,
    resolve_authority,
    roles_for,
    validate_delegation,
    validate_exception_request,
)

router = APIRouter(prefix="/v1/authority", tags=["authority"], dependencies=[Depends(require_orchestrator)])


@router.get("/overview")
def overview(db: Annotated[Session, Depends(get_db)]):
    expired = expire_authority(db)
    policy = active_policy(db)
    delegations = db.scalars(select(AuthorityDelegation).where(AuthorityDelegation.policy_id == policy.id).order_by(AuthorityDelegation.created_at.desc())).all()
    exceptions = db.scalars(select(AuthorityException).where(AuthorityException.policy_id == policy.id).order_by(AuthorityException.created_at.desc())).all()
    db.commit()
    return {"policy": policy, "delegations": delegations, "exceptions": exceptions, "expired": expired}


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def create_policy(payload: AuthorityPolicyCreate, db: Annotated[Session, Depends(get_db)]):
    document = payload.manifest.model_dump(mode="json")
    if canonical_digest(document) != payload.manifest_digest:
        raise HTTPException(status_code=422, detail="Authority policy digest mismatch.")
    existing = db.scalar(
        select(AuthorityPolicySnapshot).where(
            AuthorityPolicySnapshot.manifest_digest == payload.manifest_digest
        )
    )
    if existing is not None:
        return existing
    policy = AuthorityPolicySnapshot(
        policy_key=payload.manifest.policy_key,
        version=payload.manifest.version,
        status="draft",
        manifest=document,
        manifest_digest=payload.manifest_digest,
        created_by=payload.created_by,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/policies/{policy_id}/activate")
def activate(policy_id: UUID, payload: AuthorityPolicyActivation, db: Annotated[Session, Depends(get_db)]):
    policy = db.get(AuthorityPolicySnapshot, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Authority policy not found.")
    current = db.scalar(
        select(AuthorityPolicySnapshot).where(AuthorityPolicySnapshot.status == "active")
    )
    if current is not None and current.id != policy.id:
        resolve_authority(
            db,
            AuthorityResolutionRequest(
                actor=payload.actor,
                decision_type="policy-activation",
                action="activate",
                object_type="authority-policy",
                object_id=str(policy.id),
                object_digest=policy.manifest_digest,
                risk_level=3,
                environment="internal",
                requester=policy.created_by,
                scope={"policy_key": policy.policy_key, "version": policy.version},
            ),
        )
    activate_policy(db, policy, payload.actor)
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/resolve", status_code=status.HTTP_201_CREATED)
def resolve(payload: AuthorityResolutionRequest, db: Annotated[Session, Depends(get_db)]):
    record = resolve_authority(db, payload)
    db.commit()
    db.refresh(record)
    return record


@router.post("/delegations", status_code=status.HTTP_201_CREATED)
def create_delegation(payload: DelegationCreate, db: Annotated[Session, Depends(get_db)]):
    policy = active_policy(db)
    delegation = AuthorityDelegation(policy_id=policy.id, status="active", **payload.model_dump())
    validate_delegation(db, delegation)
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


@router.post("/delegations/{delegation_id}/revoke")
def revoke_delegation(delegation_id: UUID, payload: AuthorityPolicyActivation, db: Annotated[Session, Depends(get_db)]):
    delegation = db.get(AuthorityDelegation, delegation_id)
    if delegation is None:
        raise HTTPException(status_code=404, detail="Delegation not found.")
    if delegation.status != "active":
        raise HTTPException(status_code=409, detail="Delegation is not active.")
    if payload.actor != delegation.grantor_actor and "governance" not in roles_for(AuthorityPolicyManifest.model_validate(active_policy(db).manifest), payload.actor):
        raise HTTPException(status_code=403, detail="Actor cannot revoke this delegation.")
    delegation.status = "revoked"
    delegation.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(delegation)
    return delegation


@router.post("/exceptions", status_code=status.HTTP_201_CREATED)
def create_exception(payload: ExceptionCreate, db: Annotated[Session, Depends(get_db)]):
    policy = active_policy(db)
    document = payload.model_dump(mode="json")
    exception = AuthorityException(
        policy_id=policy.id,
        status="pending",
        record_digest=canonical_digest({"policy_digest": policy.manifest_digest, **document}),
        **payload.model_dump(),
    )
    validate_exception_request(AuthorityPolicyManifest.model_validate(policy.manifest), exception)
    db.add(exception)
    db.commit()
    db.refresh(exception)
    return exception


@router.post("/exceptions/{exception_id}/decide")
def decide_exception(exception_id: UUID, payload: ExceptionDecision, db: Annotated[Session, Depends(get_db)]):
    exception = db.get(AuthorityException, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Authority exception not found.")
    if exception.status not in {"pending", "approved"}:
        raise HTTPException(status_code=409, detail="Exception is already terminal.")
    manifest = AuthorityPolicyManifest.model_validate(active_policy(db).manifest)
    governance = roles_for(manifest, payload.actor)
    if "governance" not in governance or payload.actor in {exception.requester, exception.independent_reviewer}:
        raise HTTPException(status_code=403, detail="Exception approval requires an independent governance authority.")
    now = datetime.now(UTC)
    if payload.action == "approve":
        exception.status = "approved"
        exception.approver = payload.actor
        exception.effective_from = now
    elif payload.action == "reject":
        exception.status = "rejected"
        exception.approver = payload.actor
        exception.closed_at = now
        exception.terminal_disposition = payload.reason
    else:
        exception.status = "closed"
        exception.closed_at = now
        exception.terminal_disposition = payload.reason
    db.commit()
    db.refresh(exception)
    return exception
