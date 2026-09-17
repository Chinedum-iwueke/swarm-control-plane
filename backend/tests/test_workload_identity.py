from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from app.schemas.workload_identity import (
    WorkloadEmergencyGrantCreate,
    WorkloadIdentityCreate,
)
from app.services.workload_identity import authorize, required_scope, scopes_for_package
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError


def test_scope_derivation_and_route_authorization_are_explicit():
    manifest = {
        "task_types": [
            "research_experiment",
            "fleet_observation",
            "infrastructure_change",
        ]
    }
    scopes = scopes_for_package(manifest)
    assert {
        "task:lease",
        "research:write",
        "fleet:write",
        "infrastructure:broker",
    }.issubset(scopes)
    assert required_scope("POST", "/v1/agent/tasks/lease") == "task:lease"
    assert (
        required_scope("POST", "/v1/agent/tasks/abc/broker-ticket")
        == "infrastructure:broker"
    )


def test_identity_scopes_reject_wildcards_and_duplicates():
    base = {
        "agent_id": uuid4(),
        "charter_id": uuid4(),
        "package_id": uuid4(),
        "version": "1",
        "audience": "api",
        "accountable_owner": "ops",
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "created_by": "founder",
    }
    with pytest.raises(ValueError):
        WorkloadIdentityCreate(**base, scopes=["task:*"])
    with pytest.raises(ValueError):
        WorkloadIdentityCreate(**base, scopes=["task:lease", "task:lease"])


def test_emergency_access_requires_separation_and_is_bounded_by_schema():
    with pytest.raises(ValueError):
        WorkloadEmergencyGrantCreate(
            identity_id=uuid4(),
            scopes=["task:halt"],
            reason="urgent isolation required",
            approved_by="founder",
            independent_reviewer="founder",
            approval_reference="x",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )


def test_authorization_receipt_redacts_sensitive_context():
    identity = SimpleNamespace(id=uuid4(), status="active", scopes=["identity:read"])
    credential = SimpleNamespace(token_prefix="abc")
    db = MagicMock()
    db.get.return_value = identity
    db.scalar.return_value = credential
    payload = SimpleNamespace(
        identity_id=identity.id,
        credential_prefix="abc",
        action="read",
        required_scope="secret:read",
        context={
            "secret_value": "never-store",
            "token_hint": "never-store",
            "purpose": "test",
        },
    )
    receipt = authorize(db, payload)
    assert receipt.allowed is False
    assert receipt.context == {"purpose": "test"}
    assert "never-store" not in str(receipt.context)


def test_unknown_identity_does_not_create_orphan_receipt():
    db = MagicMock()
    db.get.return_value = None
    db.scalar.return_value = None
    payload = SimpleNamespace(
        identity_id=uuid4(),
        credential_prefix="abc",
        action="read",
        required_scope="identity:read",
        context={},
    )
    with pytest.raises(HTTPException) as exc:
        authorize(db, payload)
    assert exc.value.status_code == 404
    db.add.assert_not_called()


def test_duplicate_identity_version_returns_conflict_instead_of_server_error():
    from app.api.routes.workload_identities import create

    db = MagicMock()
    payload = MagicMock()
    collision = IntegrityError("insert", {}, RuntimeError("duplicate"))

    with patch(
        "app.api.routes.workload_identities.create_identity",
        side_effect=collision,
    ), pytest.raises(HTTPException) as exc:
        create(payload, db)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Workload identity agent/version is already registered."
    db.rollback.assert_called_once_with()
