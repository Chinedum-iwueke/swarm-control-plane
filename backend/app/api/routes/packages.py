from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import Agent, PackageDeployment, RolePackage
from app.schemas import (
    AgentPackageDeployment,
    PackageDeploymentCreate,
    PackageDeploymentResponse,
    RolePackageCreate,
    RolePackageResponse,
)
from app.services.packages import verify_package

router = APIRouter(prefix="/v1/packages", tags=["role-packages"])
agent_router = APIRouter(prefix="/v1/agent", tags=["agent-runtime"])


@router.post(
    "",
    dependencies=[Depends(require_orchestrator)],
    response_model=RolePackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_package(
    payload: RolePackageCreate,
    db: Annotated[Session, Depends(get_db)],
) -> RolePackageResponse:
    verify_package(payload, get_settings().package_signing_secret)
    package = RolePackage(
        name=payload.manifest.name,
        version=payload.manifest.version,
        manifest=payload.manifest.model_dump(mode="json"),
        manifest_digest=payload.manifest_digest,
        signature=payload.signature,
        source_repository=payload.source_repository,
        source_commit=payload.source_commit,
        created_by=payload.created_by,
    )
    db.add(package)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Package name/version or digest is already registered.",
        ) from exc
    db.refresh(package)
    return RolePackageResponse.model_validate(package)


@router.get(
    "",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[RolePackageResponse],
)
def list_packages(
    db: Annotated[Session, Depends(get_db)],
) -> list[RolePackageResponse]:
    packages = db.scalars(
        select(RolePackage).order_by(RolePackage.name, RolePackage.version)
    ).all()
    return [RolePackageResponse.model_validate(package) for package in packages]


@router.post(
    "/deployments",
    dependencies=[Depends(require_orchestrator)],
    response_model=PackageDeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def deploy_package(
    payload: PackageDeploymentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> PackageDeploymentResponse:
    agent = db.get(Agent, payload.agent_id)
    package = db.get(RolePackage, payload.package_id)
    if agent is None or package is None:
        raise HTTPException(status_code=404, detail="Agent or package not found.")
    manifest = package.manifest
    if agent.machine not in manifest["allowed_machines"]:
        raise HTTPException(status_code=422, detail="Package does not allow this machine.")
    if agent.risk_ceiling > manifest["risk_ceiling"]:
        raise HTTPException(
            status_code=422, detail="Agent risk ceiling exceeds package ceiling."
        )
    if not set(manifest["required_capabilities"]).issubset(agent.capabilities):
        raise HTTPException(status_code=422, detail="Agent lacks package capabilities.")
    deployment = PackageDeployment(**payload.model_dump())
    db.add(deployment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Deployment already exists.") from exc
    db.refresh(deployment)
    return PackageDeploymentResponse.model_validate(deployment)


@router.get(
    "/deployments",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[AgentPackageDeployment],
)
def list_deployments(
    db: Annotated[Session, Depends(get_db)],
) -> list[AgentPackageDeployment]:
    return _deployment_rows(db, None)


@router.post(
    "/deployments/{deployment_id}/revoke",
    dependencies=[Depends(require_orchestrator)],
    response_model=PackageDeploymentResponse,
)
def revoke_deployment(
    deployment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PackageDeploymentResponse:
    deployment = db.get(PackageDeployment, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if deployment.is_active:
        deployment.is_active = False
        deployment.revoked_at = datetime.now(UTC)
        db.commit()
        db.refresh(deployment)
    return PackageDeploymentResponse.model_validate(deployment)


@agent_router.get(
    "/package-deployments",
    response_model=list[AgentPackageDeployment],
)
def get_agent_deployments(
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AgentPackageDeployment]:
    return _deployment_rows(db, agent.id, active_only=True)


def _deployment_rows(
    db: Session,
    agent_id: UUID | None,
    *,
    active_only: bool = False,
) -> list[AgentPackageDeployment]:
    query = select(PackageDeployment, RolePackage).join(
        RolePackage, RolePackage.id == PackageDeployment.package_id
    )
    if agent_id is not None:
        query = query.where(PackageDeployment.agent_id == agent_id)
    if active_only:
        query = query.where(PackageDeployment.is_active.is_(True))
    rows = db.execute(query.order_by(PackageDeployment.deployed_at)).all()
    return [
        AgentPackageDeployment(
            deployment=PackageDeploymentResponse.model_validate(deployment),
            package=RolePackageResponse.model_validate(package),
        )
        for deployment, package in rows
    ]
