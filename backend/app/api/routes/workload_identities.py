from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import (
    AgentCredential,
    WorkloadEmergencyGrant,
    WorkloadIdentity,
    WorkloadSecretPolicy,
)
from app.schemas.workload_identity import (
    WorkloadAuthorizationRequest,
    WorkloadAuthorizationResponse,
    WorkloadCredentialBinding,
    WorkloadCredentialRotation,
    WorkloadCredentialRotationResponse,
    WorkloadEmergencyGrantCreate,
    WorkloadEnforcementActivation,
    WorkloadEnforcementResponse,
    WorkloadIdentityCreate,
    WorkloadIdentityResponse,
    WorkloadLifecycleAction,
    WorkloadLifecycleOverview,
    WorkloadSecretPolicyCreate,
)
from app.services.workload_identity import (
    EMERGENCY_SCOPES,
    activate_enforcement,
    append_event,
    authorize,
    bind_credentials,
    control,
    create_identity,
    digest,
    finalize_rotation,
    rotate,
)

router = APIRouter(
    prefix="/v1/workload-identities",
    tags=["workload-identities"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "", response_model=WorkloadIdentityResponse, status_code=status.HTTP_201_CREATED
)
def create(payload: WorkloadIdentityCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        identity = create_identity(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Workload identity agent/version is already registered.",
        ) from exc
    db.refresh(identity)
    return identity


@router.get("", response_model=list[WorkloadIdentityResponse])
def list_identities(db: Annotated[Session, Depends(get_db)]):
    return db.scalars(
        select(WorkloadIdentity).order_by(WorkloadIdentity.created_at)
    ).all()


@router.post("/{identity_id}/bind-credentials")
def bind(
    identity_id: UUID,
    payload: WorkloadCredentialBinding,
    db: Annotated[Session, Depends(get_db)],
):
    identity = db.get(WorkloadIdentity, identity_id)
    if not identity:
        raise HTTPException(404, "Workload identity not found.")
    count = bind_credentials(db, identity, payload.actor)
    db.commit()
    return {"identity_id": identity.id, "bound_credentials": count}


@router.post("/enforcement/activate", response_model=WorkloadEnforcementResponse)
def activate(
    payload: WorkloadEnforcementActivation, db: Annotated[Session, Depends(get_db)]
):
    result = activate_enforcement(db, payload.activated_by)
    db.commit()
    return result


@router.post("/authorize", response_model=WorkloadAuthorizationResponse)
def authorization(
    payload: WorkloadAuthorizationRequest, db: Annotated[Session, Depends(get_db)]
):
    receipt = authorize(db, payload)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/secret-policies", status_code=201)
def secret_policy(
    payload: WorkloadSecretPolicyCreate, db: Annotated[Session, Depends(get_db)]
):
    identity = db.get(WorkloadIdentity, payload.identity_id)
    if not identity or payload.required_scope not in identity.scopes:
        raise HTTPException(
            422, "Secret policy scope must belong to the workload identity."
        )
    body = payload.model_dump(mode="json")
    policy = WorkloadSecretPolicy(
        **payload.model_dump(mode="python"), status="active", policy_digest=digest(body)
    )
    db.add(policy)
    append_event(
        db,
        identity,
        "secret_policy_registered",
        payload.created_by,
        {
            "logical_name": payload.logical_name,
            "policy_digest": policy.policy_digest,
            "reference_scheme": payload.reference.split(":", 1)[0],
        },
    )
    db.commit()
    db.refresh(policy)
    return {
        "id": policy.id,
        "logical_name": policy.logical_name,
        "policy_digest": policy.policy_digest,
        "rotation_due_at": policy.rotation_due_at,
        "expires_at": policy.expires_at,
        "status": policy.status,
    }


@router.post("/secret-policies/{policy_id}/rotate", status_code=201)
def rotate_secret_policy(
    policy_id: UUID,
    payload: WorkloadSecretPolicyCreate,
    db: Annotated[Session, Depends(get_db)],
):
    prior = db.get(WorkloadSecretPolicy, policy_id)
    if prior is None:
        raise HTTPException(404, "Secret policy not found.")
    if prior.status != "active":
        raise HTTPException(409, "Only an active secret policy can rotate.")
    if (
        payload.identity_id != prior.identity_id
        or payload.logical_name != prior.logical_name
    ):
        raise HTTPException(
            422, "Secret rotation must preserve workload identity and logical name."
        )
    identity = db.get(WorkloadIdentity, prior.identity_id)
    if payload.required_scope not in identity.scopes:
        raise HTTPException(
            422, "Secret policy scope must belong to the workload identity."
        )
    body = payload.model_dump(mode="json")
    replacement = WorkloadSecretPolicy(
        **payload.model_dump(mode="python"), status="active", policy_digest=digest(body)
    )
    prior.status = "rotated"
    db.add(replacement)
    db.flush()
    append_event(
        db,
        identity,
        "secret_policy_rotated",
        payload.created_by,
        {
            "logical_name": prior.logical_name,
            "prior_policy_digest": prior.policy_digest,
            "replacement_policy_digest": replacement.policy_digest,
        },
    )
    db.commit()
    db.refresh(replacement)
    return {
        "id": replacement.id,
        "prior_policy_id": prior.id,
        "status": replacement.status,
        "policy_digest": replacement.policy_digest,
    }


@router.post("/secret-policies/{policy_id}/revoke")
def revoke_secret_policy(
    policy_id: UUID,
    payload: WorkloadLifecycleAction,
    db: Annotated[Session, Depends(get_db)],
):
    policy = db.get(WorkloadSecretPolicy, policy_id)
    if policy is None:
        raise HTTPException(404, "Secret policy not found.")
    if policy.status != "active":
        raise HTTPException(409, "Only an active secret policy can be revoked.")
    identity = db.get(WorkloadIdentity, policy.identity_id)
    policy.status = "revoked"
    append_event(
        db,
        identity,
        "secret_policy_revoked",
        payload.actor,
        {
            "logical_name": policy.logical_name,
            "policy_digest": policy.policy_digest,
            "reason": payload.reason,
        },
    )
    db.commit()
    return {
        "id": policy.id,
        "status": policy.status,
        "policy_digest": policy.policy_digest,
    }


@router.post("/emergency-grants", status_code=201)
def emergency_grant(
    payload: WorkloadEmergencyGrantCreate, db: Annotated[Session, Depends(get_db)]
):
    now = datetime.now(UTC)
    identity = db.get(WorkloadIdentity, payload.identity_id)
    if not identity:
        raise HTTPException(404, "Workload identity not found.")
    if not set(payload.scopes).issubset(EMERGENCY_SCOPES):
        raise HTTPException(
            422, "Emergency access is reduction-only; requested scope is prohibited."
        )
    if payload.expires_at <= now or payload.expires_at > now + timedelta(hours=1):
        raise HTTPException(422, "Emergency grant must expire within one hour.")
    body = payload.model_dump(mode="json")
    grant = WorkloadEmergencyGrant(
        **payload.model_dump(mode="python"),
        status="active",
        starts_at=now,
        record_digest=digest(body),
    )
    db.add(grant)
    append_event(
        db,
        identity,
        "emergency_grant_issued",
        payload.approved_by,
        {
            "scopes": sorted(payload.scopes),
            "expires_at": payload.expires_at.isoformat(),
            "record_digest": grant.record_digest,
        },
    )
    db.commit()
    db.refresh(grant)
    return {
        "id": grant.id,
        "status": grant.status,
        "record_digest": grant.record_digest,
        "expires_at": grant.expires_at,
    }


@router.post("/emergency-grants/{grant_id}/revoke")
def revoke_emergency_grant(
    grant_id: UUID,
    payload: WorkloadLifecycleAction,
    db: Annotated[Session, Depends(get_db)],
):
    grant = db.get(WorkloadEmergencyGrant, grant_id)
    if grant is None:
        raise HTTPException(404, "Emergency grant not found.")
    if grant.status != "active":
        raise HTTPException(409, "Only an active emergency grant can be revoked.")
    identity = db.get(WorkloadIdentity, grant.identity_id)
    grant.status = "revoked"
    grant.revoked_at = datetime.now(UTC)
    append_event(
        db,
        identity,
        "emergency_grant_revoked",
        payload.actor,
        {"record_digest": grant.record_digest, "reason": payload.reason},
    )
    db.commit()
    return {
        "id": grant.id,
        "status": grant.status,
        "record_digest": grant.record_digest,
    }


@router.post(
    "/{identity_id}/credentials/rotate",
    response_model=WorkloadCredentialRotationResponse,
)
def rotate_credential(
    identity_id: UUID,
    payload: WorkloadCredentialRotation,
    db: Annotated[Session, Depends(get_db)],
):
    identity = db.get(WorkloadIdentity, identity_id)
    if not identity:
        raise HTTPException(404, "Workload identity not found.")
    credential, token, prior = rotate(
        db, identity, payload.actor, payload.overlap_seconds
    )
    db.commit()
    db.refresh(credential)
    return WorkloadCredentialRotationResponse(
        identity_id=identity.id,
        credential_id=credential.id,
        token=token,
        token_prefix=credential.token_prefix,
        expires_at=credential.expires_at,
        prior_credential_id=prior.id,
        overlap_expires_at=prior.overlap_expires_at,
    )


@router.post("/{identity_id}/credentials/finalize")
def finalize(
    identity_id: UUID,
    payload: WorkloadCredentialBinding,
    db: Annotated[Session, Depends(get_db)],
):
    identity = db.get(WorkloadIdentity, identity_id)
    if not identity:
        raise HTTPException(404, "Workload identity not found.")
    finalize_rotation(db, identity, payload.actor)
    db.commit()
    return {"status": "finalized"}


@router.post("/{identity_id}/credentials/rollback")
def rollback(
    identity_id: UUID,
    payload: WorkloadCredentialBinding,
    db: Annotated[Session, Depends(get_db)],
):
    identity = db.get(WorkloadIdentity, identity_id)
    if not identity:
        raise HTTPException(404, "Workload identity not found.")
    finalize_rotation(db, identity, payload.actor, rollback=True)
    db.commit()
    return {"status": "rolled_back"}


@router.get("/overview", response_model=WorkloadLifecycleOverview)
def overview(db: Annotated[Session, Depends(get_db)]):
    now = datetime.now(UTC)
    identities = db.scalars(
        select(WorkloadIdentity).order_by(WorkloadIdentity.created_at)
    ).all()
    return WorkloadLifecycleOverview(
        enforcement_active=control(db).enforcement_active,
        identities=identities,
        active_secret_policies=db.scalar(
            select(func.count())
            .select_from(WorkloadSecretPolicy)
            .where(WorkloadSecretPolicy.status == "active")
        )
        or 0,
        active_emergency_grants=db.scalar(
            select(func.count())
            .select_from(WorkloadEmergencyGrant)
            .where(
                WorkloadEmergencyGrant.status == "active",
                WorkloadEmergencyGrant.expires_at > now,
            )
        )
        or 0,
        expiring_credentials=db.scalar(
            select(func.count())
            .select_from(AgentCredential)
            .where(
                AgentCredential.revoked_at.is_(None),
                AgentCredential.expires_at <= now + timedelta(days=14),
            )
        )
        or 0,
    )
