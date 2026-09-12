from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.authority import AuthorityPolicyManifest, AuthorityResolutionRequest
from app.services.authority import (
    activate_policy,
    pure_resolution,
    validate_exception_request,
)
from fastapi import HTTPException


def manifest() -> AuthorityPolicyManifest:
    return AuthorityPolicyManifest.model_validate(
        {
            "schema_version": "authority-policy-v1.0.0",
            "policy_key": "institutional-authority",
            "version": "1.0.0",
            "roles": [
                {"role": "governance", "actors": ["founder-operator"]},
                {"role": "risk", "actors": ["risk-reviewer"]},
            ],
            "identity_aliases": {
                "founder-mission-control": "founder-operator",
                "founder-telegram": "founder-operator",
            },
            "decisions": [
                {
                    "decision_type": "task-approval",
                    "actions": ["approve"],
                    "accountable_roles": ["governance"],
                    "veto_roles": ["risk"],
                    "environments": ["internal"],
                    "maximum_risk": 3,
                    "delegable": True,
                    "constitutional": False,
                    "separation": [
                        {
                            "field": "requester",
                            "minimum_risk": 2,
                            "rule_key": "no-consequential-self-approval",
                        }
                    ],
                },
                {
                    "decision_type": "capital-allocation",
                    "actions": ["allocate"],
                    "accountable_roles": ["governance"],
                    "veto_roles": ["risk"],
                    "environments": ["production"],
                    "maximum_risk": 3,
                    "delegable": False,
                    "constitutional": True,
                    "separation": [
                        {
                            "field": "requester",
                            "minimum_risk": 0,
                            "rule_key": "human-capital-authority",
                        }
                    ],
                },
            ],
            "constitutional_boundaries": ["human-capital-authority"],
        }
    )


def request(**updates) -> AuthorityResolutionRequest:
    values = {
        "actor": "founder-operator",
        "decision_type": "task-approval",
        "action": "approve",
        "object_type": "task",
        "object_id": "task-1",
        "object_digest": "a" * 64,
        "risk_level": 1,
        "environment": "internal",
        "requester": "planner-service",
    }
    values.update(updates)
    return AuthorityResolutionRequest.model_validate(values)


def test_authorized_actor_resolves_against_explicit_right() -> None:
    allowed, reason, roles, failures = pure_resolution(manifest(), request())
    assert allowed is True
    assert reason == "authorized"
    assert roles == ["governance"]
    assert failures == []


def test_mission_control_channel_resolves_to_founder_authority() -> None:
    allowed, reason, roles, failures = pure_resolution(
        manifest(), request(actor="founder-mission-control")
    )
    assert allowed is True
    assert reason == "authorized"
    assert roles == ["governance"]
    assert failures == []


def test_alias_cannot_bypass_consequential_self_approval() -> None:
    allowed, reason, _, failures = pure_resolution(
        manifest(),
        request(actor="founder-telegram", requester="founder-operator", risk_level=3),
    )
    assert allowed is False
    assert reason == "separation:no-consequential-self-approval"
    assert failures == ["separation:no-consequential-self-approval"]


def test_registered_exception_can_cover_operating_separation_only() -> None:
    allowed, _, _, _ = pure_resolution(
        manifest(),
        request(requester="founder-operator", risk_level=3),
        exception_rule="no-consequential-self-approval",
    )
    assert allowed is True


def test_active_veto_fails_closed() -> None:
    allowed, reason, _, _ = pure_resolution(
        manifest(), request(active_veto_roles=["risk"])
    )
    assert allowed is False
    assert reason == "active-veto:risk"


def test_conflicting_delegations_fail_closed() -> None:
    allowed, reason, _, failures = pure_resolution(
        manifest(),
        request(actor="temporary-approver"),
        delegated=False,
        delegation_conflict=True,
    )
    assert allowed is False
    assert reason == "conflicting-delegations"
    assert "actor-lacks-accountable-role" in failures


def test_emergency_authority_is_reduction_only() -> None:
    document = manifest().model_dump(mode="json")
    document["decisions"].append(
        {
            "decision_type": "emergency-containment",
            "actions": ["halt", "isolate", "reduce"],
            "accountable_roles": ["governance"],
            "veto_roles": [],
            "environments": ["*"],
            "maximum_risk": 3,
            "delegable": True,
            "constitutional": True,
            "separation": [],
        }
    )
    emergency = AuthorityPolicyManifest.model_validate(document)
    allowed, _, _, _ = pure_resolution(
        emergency,
        request(decision_type="emergency-containment", action="halt"),
    )
    expanded, reason, _, _ = pure_resolution(
        emergency,
        request(decision_type="emergency-containment", action="expand"),
    )
    assert allowed is True
    assert expanded is False
    assert reason == "action-not-authorized"


def test_constitutional_boundary_cannot_be_excepted() -> None:
    exception = SimpleNamespace(
        requester="founder-operator",
        independent_reviewer="risk-reviewer",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        rule_key="human-capital-authority",
    )
    with pytest.raises(HTTPException, match="Constitutional boundaries"):
        validate_exception_request(manifest(), exception)


def test_exception_requires_independent_reviewer_and_bounded_expiry() -> None:
    exception = SimpleNamespace(
        requester="founder-operator",
        independent_reviewer="founder-operator",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        rule_key="no-consequential-self-approval",
    )
    with pytest.raises(HTTPException, match="independent"):
        validate_exception_request(manifest(), exception)


def test_policy_activation_flushes_retirement_before_new_activation() -> None:
    current = SimpleNamespace(
        id="current-policy", status="active", effective_until=None
    )
    candidate = SimpleNamespace(
        id="candidate-policy",
        status="draft",
        effective_from=None,
        effective_until=None,
        activated_by=None,
        activated_at=None,
        supersedes_id=None,
    )
    db = MagicMock()
    db.scalar.return_value = current
    activate_policy(db, candidate, "founder-operator", datetime.now(UTC))
    db.flush.assert_called_once_with()
    assert current.status == "retired"
    assert candidate.status == "active"
    assert candidate.supersedes_id == current.id
