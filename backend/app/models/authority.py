import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuthorityPolicySnapshot(Base):
    __tablename__ = "authority_policy_snapshots"
    __table_args__ = (UniqueConstraint("policy_key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[str | None] = mapped_column(String(150))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_policy_snapshots.id"))
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthorityDelegation(Base):
    __tablename__ = "authority_delegations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_policy_snapshots.id"), nullable=False, index=True)
    grantor_actor: Mapped[str] = mapped_column(String(150), nullable=False)
    grantee_actor: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    decision_types: Mapped[list] = mapped_column(JSONB, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    max_risk: Mapped[int] = mapped_column(Integer, nullable=False)
    environment: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthorityException(Base):
    __tablename__ = "authority_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_policy_snapshots.id"), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(120), nullable=False)
    requester: Mapped[str] = mapped_column(String(150), nullable=False)
    approver: Mapped[str | None] = mapped_column(String(150))
    independent_reviewer: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False)
    compensating_controls: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_disposition: Mapped[str | None] = mapped_column(Text)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthorityDecisionRecord(Base):
    __tablename__ = "authority_decision_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_policy_snapshots.id"), nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[str] = mapped_column(String(200), nullable=False)
    object_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    effective_roles: Mapped[list] = mapped_column(JSONB, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    delegation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_delegations.id"))
    exception_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("authority_exceptions.id"))
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
