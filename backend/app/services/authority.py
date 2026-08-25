from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authority import (
    AuthorityDecisionRecord,
    AuthorityDelegation,
    AuthorityException,
    AuthorityPolicySnapshot,
)
from app.models.governance import TaskApproval
from app.schemas.authority import (
    AuthorityPolicyManifest,
    AuthorityResolutionRequest,
    DecisionRight,
)

MAX_DELEGATION = timedelta(days=30)
MAX_EXCEPTION = timedelta(hours=24)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def active_policy(db: Session, now: datetime | None = None) -> AuthorityPolicySnapshot:
    now = now or datetime.now(UTC)
    policy = db.scalar(
        select(AuthorityPolicySnapshot).where(
            AuthorityPolicySnapshot.status == "active",
            AuthorityPolicySnapshot.effective_from <= now,
            (AuthorityPolicySnapshot.effective_until.is_(None) | (AuthorityPolicySnapshot.effective_until > now)),
        )
    )
    if policy is None:
        raise HTTPException(status_code=409, detail="No active authority policy.")
    return policy


def activate_policy(db: Session, policy: AuthorityPolicySnapshot, actor: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if policy.status not in {"draft", "retired"}:
        raise HTTPException(status_code=409, detail="Policy cannot be activated from its current state.")
    current = db.scalar(select(AuthorityPolicySnapshot).where(AuthorityPolicySnapshot.status == "active"))
    if current is not None:
        current.status = "retired"
        current.effective_until = now
        policy.supersedes_id = current.id
    policy.status = "active"
    policy.effective_from = now
    policy.effective_until = None
    policy.activated_by = actor
    policy.activated_at = now


def roles_for(manifest: AuthorityPolicyManifest, actor: str) -> set[str]:
    principal = manifest.identity_aliases.get(actor, actor)
    return {binding.role for binding in manifest.roles if principal in binding.actors}


def principal_for(manifest: AuthorityPolicyManifest, actor: str | None) -> str | None:
    return manifest.identity_aliases.get(actor, actor) if actor else None


def decision_rule(manifest: AuthorityPolicyManifest, decision_type: str) -> DecisionRight | None:
    return next((item for item in manifest.decisions if item.decision_type == decision_type), None)


def pure_resolution(
    manifest: AuthorityPolicyManifest,
    request: AuthorityResolutionRequest,
    *,
    delegated: bool = False,
    delegation_conflict: bool = False,
    exception_rule: str | None = None,
) -> tuple[bool, str, list[str], list[str]]:
    roles = roles_for(manifest, request.actor)
    rule = decision_rule(manifest, request.decision_type)
    failures: list[str] = []
    if delegation_conflict:
        failures.append("conflicting-delegations")
    if rule is None:
        failures.append("decision-type-unregistered")
        return False, failures[0], sorted(roles), failures
    if request.action not in rule.actions:
        failures.append("action-not-authorized")
    if request.risk_level > rule.maximum_risk:
        failures.append("risk-exceeds-authority")
    if "*" not in rule.environments and request.environment not in rule.environments:
        failures.append("environment-out-of-scope")
    if not roles.intersection(rule.accountable_roles) and not delegated:
        failures.append("actor-lacks-accountable-role")
    active_vetoes = sorted(set(request.active_veto_roles).intersection(rule.veto_roles))
    if active_vetoes:
        failures.append("active-veto:" + ",".join(active_vetoes))
    for separation in rule.separation:
        participant = principal_for(manifest, getattr(request, separation.field))
        actor = principal_for(manifest, request.actor)
        if (
            request.risk_level >= separation.minimum_risk
            and participant == actor
            and (rule.constitutional or exception_rule != separation.rule_key)
        ):
            failures.append("separation:" + separation.rule_key)
    return not failures, "authorized" if not failures else failures[0], sorted(roles), failures


def resolve_authority(db: Session, request: AuthorityResolutionRequest, now: datetime | None = None) -> AuthorityDecisionRecord:
    now = now or datetime.now(UTC)
    policy = active_policy(db, now)
    manifest = AuthorityPolicyManifest.model_validate(policy.manifest)
    rule = decision_rule(manifest, request.decision_type)
    delegation = None
    if rule is not None and rule.delegable:
        delegations = db.scalars(
            select(AuthorityDelegation).where(
                AuthorityDelegation.policy_id == policy.id,
                AuthorityDelegation.grantee_actor == request.actor,
                AuthorityDelegation.status == "active",
                AuthorityDelegation.expires_at > now,
            )
        ).all()
        applicable = [
            item
            for item in delegations
            if request.decision_type in item.decision_types
            and request.risk_level <= item.max_risk
            and item.environment in {"*", request.environment}
        ]
        delegation = applicable[0] if len(applicable) == 1 else None
        delegation_conflict = len(applicable) > 1
    else:
        delegation_conflict = False
    exception = db.get(AuthorityException, request.exception_id) if request.exception_id else None
    exception_rule = None
    if (
        exception is not None
        and exception.policy_id == policy.id
        and exception.status == "approved"
        and exception.effective_from is not None
        and exception.effective_from <= now < exception.expires_at
    ):
        exception_rule = exception.rule_key
    allowed, reason, roles, failures = pure_resolution(
        manifest,
        request,
        delegated=delegation is not None,
        delegation_conflict=delegation_conflict,
        exception_rule=exception_rule,
    )
    body = {
        "policy_digest": policy.manifest_digest,
        "decision_type": request.decision_type,
        "action": request.action,
        "object_type": request.object_type,
        "object_id": request.object_id,
        "object_digest": request.object_digest,
        "actor": request.actor,
        "roles": roles,
        "scope": request.scope,
        "risk_level": request.risk_level,
        "outcome": "authorized" if allowed else "denied",
        "reason": reason,
        "failures": failures,
        "delegation_id": str(delegation.id) if delegation else None,
        "exception_id": str(exception.id) if exception_rule and exception else None,
        "resolved_at": now.isoformat(),
    }
    record = AuthorityDecisionRecord(
        policy_id=policy.id,
        decision_type=request.decision_type,
        action=request.action,
        object_type=request.object_type,
        object_id=request.object_id,
        object_digest=request.object_digest,
        actor=request.actor,
        effective_roles=roles,
        scope=request.scope,
        risk_level=request.risk_level,
        outcome=body["outcome"],
        reason=reason,
        evidence={"failures": failures, "policy_digest": policy.manifest_digest},
        delegation_id=delegation.id if delegation else None,
        exception_id=exception.id if exception_rule and exception else None,
        record_digest=canonical_digest(body),
    )
    db.add(record)
    db.flush()
    if not allowed:
        db.commit()
        raise HTTPException(status_code=403, detail={"reason": reason, "decision_record_id": str(record.id)})
    return record


def resolve_task_approval(
    db: Session,
    approval: TaskApproval,
    *,
    actor: str,
    action: str,
    exception_id: UUID | None = None,
) -> AuthorityDecisionRecord:
    return resolve_authority(
        db,
        AuthorityResolutionRequest(
            actor=actor,
            decision_type="task-approval",
            action=action,
            object_type="task-approval",
            object_id=str(approval.id),
            object_digest=approval.plan_digest,
            scope=approval.scope,
            risk_level=approval.risk_level,
            environment=(approval.scope or {}).get("environment", "internal"),
            requester=approval.requested_by,
            exception_id=exception_id,
        ),
    )


def validate_delegation(db: Session, delegation: AuthorityDelegation, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    policy = active_policy(db, now)
    manifest = AuthorityPolicyManifest.model_validate(policy.manifest)
    if delegation.grantor_actor == delegation.grantee_actor:
        raise HTTPException(status_code=422, detail="Self-delegation is forbidden.")
    if delegation.expires_at <= now or delegation.expires_at > now + MAX_DELEGATION:
        raise HTTPException(status_code=422, detail="Delegation expiry is outside the bounded interval.")
    grantor_roles = roles_for(manifest, delegation.grantor_actor)
    for decision_type in delegation.decision_types:
        rule = decision_rule(manifest, decision_type)
        if rule is None or not rule.delegable or not grantor_roles.intersection(rule.accountable_roles):
            raise HTTPException(status_code=403, detail=f"Grantor cannot delegate {decision_type}.")
        if delegation.max_risk > rule.maximum_risk:
            raise HTTPException(status_code=422, detail="Delegation exceeds the parent risk boundary.")


def validate_exception_request(manifest: AuthorityPolicyManifest, exception: AuthorityException, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if exception.requester == exception.independent_reviewer:
        raise HTTPException(status_code=422, detail="Exception review must be independent.")
    if exception.expires_at <= now or exception.expires_at > now + MAX_EXCEPTION:
        raise HTTPException(status_code=422, detail="Exception expiry is outside the bounded interval.")
    if exception.rule_key in manifest.constitutional_boundaries:
        raise HTTPException(status_code=422, detail="Constitutional boundaries cannot be excepted.")
    known_rules = {item.rule_key for rule in manifest.decisions for item in rule.separation}
    if exception.rule_key not in known_rules:
        raise HTTPException(status_code=422, detail="Exception rule is not registered as waivable.")


def expire_authority(db: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    delegations = db.scalars(select(AuthorityDelegation).where(AuthorityDelegation.status == "active", AuthorityDelegation.expires_at <= now)).all()
    exceptions = db.scalars(select(AuthorityException).where(AuthorityException.status == "approved", AuthorityException.expires_at <= now)).all()
    for item in delegations:
        item.status = "expired"
    for item in exceptions:
        item.status = "expired"
        item.closed_at = now
        item.terminal_disposition = "Expired automatically."
    return {"delegations": len(delegations), "exceptions": len(exceptions)}
