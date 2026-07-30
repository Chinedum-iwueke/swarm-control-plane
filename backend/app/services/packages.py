import hashlib
import hmac
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, PackageDeployment, RolePackage
from app.schemas.agent import AgentHeartbeat
from app.schemas.package import RolePackageCreate, RolePackageManifest


def canonical_manifest(manifest: RolePackageManifest | dict) -> bytes:
    document = (
        manifest.model_dump(mode="json") if isinstance(manifest, RolePackageManifest) else manifest
    )
    return json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()


def verify_package(payload: RolePackageCreate, signing_secret: str) -> None:
    document = canonical_manifest(payload.manifest)
    digest = hashlib.sha256(document).hexdigest()
    if not hmac.compare_digest(digest, payload.manifest_digest):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Manifest digest does not match canonical package content.",
        )
    expected_signature = hmac.new(
        signing_secret.encode(), document, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, payload.signature):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Package signature verification failed.",
        )


def verify_agent_package_attestation(
    db: Session,
    agent: Agent,
    heartbeat: AgentHeartbeat,
) -> None:
    digest = heartbeat.metadata.get("role_package_digest")
    name = heartbeat.metadata.get("role_package")
    version = heartbeat.metadata.get("role_package_version")
    if not all(isinstance(value, str) for value in (digest, name, version)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A complete role-package attestation is required.",
        )
    deployed = db.scalar(
        select(RolePackage)
        .join(PackageDeployment, PackageDeployment.package_id == RolePackage.id)
        .where(
            PackageDeployment.agent_id == agent.id,
            PackageDeployment.is_active.is_(True),
            RolePackage.manifest_digest == digest,
            RolePackage.name == name,
            RolePackage.version == version,
        )
    )
    if deployed is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role-package attestation does not match an active deployment.",
        )
