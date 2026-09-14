from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from app.schemas.agent_governance import (
    AgentCapabilityGrantCreate,
    AgentCharterManifest,
    EffectiveAuthorityRequest,
)
from app.services.agent_governance import digest, resolve
from app.services.tasks import resolve_task_authority
from pydantic import ValidationError


def manifest():
    return AgentCharterManifest.model_validate({
        "schema_version": "agent-charter-v1.0.0", "role": "research verifier",
        "responsibilities": ["Reproduce bounded research evidence."],
        "capabilities": ["testing"], "allowed_machines": ["vm1-developer"],
        "allowed_task_types": ["code_validation"], "allowed_repositories": ["bulletproof_bt"],
        "risk_ceiling": 1, "accountable_owner": "research-operations",
        "conflicts": [], "forbidden_actions": ["live-trading"],
    })


def test_charter_is_strict_and_digest_stable():
    value = manifest().model_dump(mode="json")
    assert digest(value) == digest(dict(reversed(list(value.items()))))
    with pytest.raises(ValidationError):
        AgentCharterManifest.model_validate({**value, "capabilities": ["testing", "testing"]})
    with pytest.raises(ValidationError):
        AgentCharterManifest.model_validate({**value, "unexpected": True})


def test_grant_requires_separate_grantor_and_owner():
    with pytest.raises(ValidationError, match="distinct"):
        AgentCapabilityGrantCreate(agent_id=uuid4(), charter_id=uuid4(), capability="testing",
            package_id=uuid4(),
            machine="vm1-developer", task_types=["code_validation"], repositories=["bulletproof_bt"],
            risk_ceiling=1, accountable_owner="founder-operator", granted_by="founder-operator",
            reason="pilot", expires_at=datetime.now(UTC) + timedelta(days=1))


def test_effective_authority_intersects_registration_charter_package_and_grant():
    agent_id = uuid4(); charter_id = uuid4()
    agent = SimpleNamespace(id=agent_id, is_enabled=True, machine="vm1-developer", capabilities=["testing"], risk_ceiling=1)
    charter = SimpleNamespace(id=charter_id, manifest=manifest().model_dump(mode="json"), manifest_digest="a" * 64)
    package = SimpleNamespace(manifest={"required_capabilities": ["testing"], "allowed_machines": ["vm1-developer"],
        "task_types": ["code_validation"], "risk_ceiling": 1, "repository_profile": {"repositories": ["bulletproof_bt"]}}, manifest_digest="b" * 64)
    package.id = uuid4()
    grant = SimpleNamespace(capability="testing", status="active", package_id=package.id, machine="vm1-developer", task_types=["code_validation"],
        repositories=["bulletproof_bt"], risk_ceiling=1, expires_at=datetime.now(UTC) + timedelta(days=1),
        accountable_owner="research-operations", record_digest="c" * 64)
    db = MagicMock(); db.get.return_value = agent; db.scalar.side_effect = [charter, package, grant]
    request = EffectiveAuthorityRequest(capability="testing", machine="vm1-developer", task_type="code_validation", repository="bulletproof_bt", risk_level=1)
    result = resolve(db, agent_id, request)
    assert result["allowed"] is True
    assert result["charter_digest"] == "a" * 64 and len(result["snapshot_digest"]) == 64


def test_expired_grant_and_conflict_fail_closed():
    agent_id = uuid4(); agent = SimpleNamespace(is_enabled=True, machine="vm1-developer", capabilities=["testing"], risk_ceiling=1)
    charter_manifest = manifest().model_dump(mode="json"); charter_manifest["conflicts"] = ["testing"]
    charter = SimpleNamespace(manifest=charter_manifest, manifest_digest="a" * 64)
    package = SimpleNamespace(manifest={"required_capabilities": ["testing"], "allowed_machines": ["vm1-developer"], "task_types": ["code_validation"], "risk_ceiling": 1, "repository_profile": {"repositories": []}}, manifest_digest="b" * 64)
    package.id = uuid4()
    grant = SimpleNamespace(package_id=package.id, machine="vm1-developer", task_types=["code_validation"], repositories=[], risk_ceiling=1,
        expires_at=datetime.now(UTC) - timedelta(seconds=1), accountable_owner="research-operations", record_digest="c" * 64)
    db = MagicMock(); db.get.return_value = agent; db.scalar.side_effect = [charter, package, grant]
    result = resolve(db, agent_id, EffectiveAuthorityRequest(capability="testing", machine="vm1-developer", task_type="code_validation", risk_level=0))
    assert result["allowed"] is False
    assert "grant-expired" in result["reasons"] and "charter-conflict-or-prohibition" in result["reasons"]


def test_task_authority_resolves_every_declared_capability():
    task = SimpleNamespace(required_capabilities=["testing", "git"], task_type="code_validation", project="bulletproof_bt", input_contract={}, risk_level=1)
    agent = SimpleNamespace(id=uuid4(), machine="vm1-developer")
    with patch("app.services.tasks.resolve_agent_authority", return_value={"allowed": True}) as resolver:
        snapshots = resolve_task_authority(MagicMock(), task, agent, datetime.now(UTC))
    assert snapshots == [{"allowed": True}, {"allowed": True}]
    assert [call.args[2].capability for call in resolver.call_args_list] == ["testing", "git"]
    assert [call.args[2].repository for call in resolver.call_args_list] == ["bulletproof_bt", "bulletproof_bt"]


def test_task_authority_uses_explicit_execution_repository_not_logical_project():
    task = SimpleNamespace(
        required_capabilities=["research-intelligence"],
        task_type="alpha_discovery",
        project="systematic-research",
        input_contract={"repository": "swarm-control-plane"},
        risk_level=0,
    )
    agent = SimpleNamespace(id=uuid4(), machine="vm1-developer")

    with patch(
        "app.services.tasks.resolve_agent_authority", return_value={"allowed": True}
    ) as resolver:
        resolve_task_authority(MagicMock(), task, agent, datetime.now(UTC))

    assert resolver.call_args.args[2].repository == "swarm-control-plane"


def test_founder_intake_planning_does_not_require_repository_execution_grant():
    agent_id = uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        is_enabled=True,
        machine="vm1-developer",
        capabilities=["founder-intake"],
        risk_ceiling=1,
    )
    charter = SimpleNamespace(
        id=uuid4(),
        manifest={
            "capabilities": ["founder-intake"],
            "allowed_machines": ["vm1-developer"],
            "allowed_task_types": ["founder_request"],
            "allowed_repositories": [],
            "risk_ceiling": 1,
            "conflicts": [],
            "forbidden_actions": [],
        },
        manifest_digest="a" * 64,
    )
    package = SimpleNamespace(
        id=uuid4(),
        manifest={
            "required_capabilities": ["founder-intake"],
            "allowed_machines": ["vm1-developer"],
            "task_types": ["founder_request"],
            "risk_ceiling": 1,
            "repository_profile": {"repositories": []},
        },
        manifest_digest="b" * 64,
    )
    grant = SimpleNamespace(
        capability="founder-intake",
        status="active",
        package_id=package.id,
        machine="vm1-developer",
        task_types=["founder_request"],
        repositories=[],
        risk_ceiling=1,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        accountable_owner="company-operations",
        record_digest="c" * 64,
    )
    db = MagicMock()
    db.get.return_value = agent
    db.scalar.side_effect = [charter, package, grant]

    result = resolve(
        db,
        agent_id,
        EffectiveAuthorityRequest(
            capability="founder-intake",
            machine="vm1-developer",
            task_type="founder_request",
            repository="bulletproof_bt",
            risk_level=1,
        ),
    )

    assert result["allowed"] is True
    assert not any("repository" in reason for reason in result["reasons"])
