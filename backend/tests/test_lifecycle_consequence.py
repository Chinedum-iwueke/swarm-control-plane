from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.schemas.lifecycle_consequence import ConsequenceCreate
from app.services.lifecycle_consequence import consequence_state
from fastapi import HTTPException
from pydantic import ValidationError


def payload(**updates):
    data = {
        "command_id": uuid4(),
        "actor": "founder-operator",
        "action": "promote",
        "dimension": "operations",
        "expected_version": 1,
        "subject_digest": "a" * 64,
        "evidence": ["b" * 64],
        "evidence_epoch": datetime.now(UTC),
        "approvers": ["founder-operator", "risk-reviewer"],
        "affected_descendants": ["candidate:child"],
        "expires_at": datetime.now(UTC) + timedelta(days=7),
        "reason": "Approve a bounded consequence with retained evidence.",
        "risk_level": 1,
        "originator": "research-execution-agent",
        "evaluator": "risk-reviewer",
    }
    data.update(updates)
    return data


@pytest.mark.parametrize(
    ("dimension", "state", "action", "result"),
    [
        ("operations", "candidate", "promote", "approved"),
        ("operations", "live", "demote", "demo"),
        ("operations", "live", "quarantine", "suspended"),
        ("operations", "suspended", "retire", "retired"),
        ("operations", "retired", "reinstate", "candidate"),
        ("evidence", "admissible", "quarantine", "disputed"),
        ("evidence", "retired", "reinstate", "admissible"),
        ("capital", "allocated", "demote", "reduced"),
    ],
)
def test_declared_consequences(dimension, state, action, result):
    assert consequence_state(dimension, state, action) == result


def test_invalid_consequence_fails_closed():
    with pytest.raises(HTTPException) as error:
        consequence_state("capital", "no-authority", "promote")
    assert error.value.status_code == 409


def test_stale_evidence_is_rejected():
    with pytest.raises(ValidationError):
        ConsequenceCreate.model_validate(
            payload(evidence_epoch=datetime.now(UTC) - timedelta(days=8))
        )


def test_promotion_requires_independent_approval():
    with pytest.raises(ValidationError):
        ConsequenceCreate.model_validate(payload(approvers=["founder-operator"]))


def test_originator_cannot_be_promotion_approver():
    with pytest.raises(ValidationError):
        ConsequenceCreate.model_validate(
            payload(approvers=["founder-operator", "research-execution-agent"])
        )


def test_expiry_is_bounded():
    with pytest.raises(ValidationError):
        ConsequenceCreate.model_validate(
            payload(expires_at=datetime.now(UTC) + timedelta(days=31))
        )


def test_evidence_references_are_digests():
    with pytest.raises(ValidationError):
        ConsequenceCreate.model_validate(payload(evidence=["not-a-digest"]))
