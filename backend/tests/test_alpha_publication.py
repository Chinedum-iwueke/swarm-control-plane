from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.services.alpha_publication import (
    _evidence,
    _has_founder_execution_authority,
    _publication_disposition,
    _require_current_projections,
    _result_metrics,
)
from app.services.evidence import canonical_payload_digest
from fastapi import HTTPException


def test_alpha_publication_requires_exact_current_projection_epochs() -> None:
    graph = SimpleNamespace(source_epoch=7)
    retrieval = SimpleNamespace(source_epoch=7, corpus_digest="a" * 64)
    corpus = SimpleNamespace(epoch=7, corpus_digest="a" * 64)

    _require_current_projections(graph, retrieval, corpus)


def test_alpha_publication_accepts_authorized_founder_channel_alias() -> None:
    approval = SimpleNamespace(id="approval-id", decided_by="founder-mission-control")
    decision = SimpleNamespace(effective_roles=["founder", "governance"])
    db = SimpleNamespace(scalar=lambda _: decision)

    assert _has_founder_execution_authority(db, approval) is True


def test_alpha_publication_rejects_non_founder_authority() -> None:
    approval = SimpleNamespace(id="approval-id", decided_by="research-reviewer")
    decision = SimpleNamespace(effective_roles=["research"], delegation_id=None)
    db = SimpleNamespace(scalar=lambda _: decision)

    assert _has_founder_execution_authority(db, approval) is False


def test_alpha_publication_accepts_valid_founder_granted_delegation() -> None:
    decided_at = datetime.now(UTC)
    approval = SimpleNamespace(id="approval-id", decided_by="bounded-operator")
    decision = SimpleNamespace(
        effective_roles=[],
        delegation_id="delegation-id",
        policy_id="policy-id",
        actor="bounded-operator",
        risk_level=1,
        created_at=decided_at,
    )
    delegation = SimpleNamespace(
        policy_id="policy-id",
        grantor_actor="founder-operator",
        grantee_actor="bounded-operator",
        decision_types=["task-approval"],
        max_risk=1,
        created_at=decided_at - timedelta(minutes=1),
        expires_at=decided_at + timedelta(hours=1),
        revoked_at=decided_at + timedelta(minutes=1),
    )
    policy = SimpleNamespace(
        manifest={
            "schema_version": "authority-policy-v1.0.0",
            "policy_key": "test-authority",
            "version": "1.0.0",
            "roles": [
                {"role": "founder", "actors": ["founder-operator"]},
                {"role": "operator", "actors": ["bounded-operator"]},
            ],
            "decisions": [
                {
                    "decision_type": "task-approval",
                    "actions": ["approve"],
                    "accountable_roles": ["founder"],
                    "maximum_risk": 1,
                    "delegable": True,
                }
            ],
            "constitutional_boundaries": ["no-self-approval"],
        }
    )
    db = MagicMock()
    db.scalar.return_value = decision
    db.get.side_effect = lambda model, identity: {
        "delegation-id": delegation,
        "policy-id": policy,
    }.get(identity)

    assert _has_founder_execution_authority(db, approval) is True


def test_alpha_publication_rejects_delegation_revoked_before_decision() -> None:
    decided_at = datetime.now(UTC)
    approval = SimpleNamespace(id="approval-id", decided_by="bounded-operator")
    decision = SimpleNamespace(
        effective_roles=[],
        delegation_id="delegation-id",
        policy_id="policy-id",
        actor="bounded-operator",
        risk_level=1,
        created_at=decided_at,
    )
    delegation = SimpleNamespace(
        policy_id="policy-id",
        grantor_actor="founder-operator",
        grantee_actor="bounded-operator",
        decision_types=["task-approval"],
        max_risk=1,
        created_at=decided_at - timedelta(minutes=2),
        expires_at=decided_at + timedelta(hours=1),
        revoked_at=decided_at - timedelta(minutes=1),
    )
    db = MagicMock()
    db.scalar.return_value = decision
    db.get.side_effect = lambda model, identity: delegation

    assert _has_founder_execution_authority(db, approval) is False


def test_alpha_publication_separates_measurements_from_search_metadata() -> None:
    trial = {
        "metrics": {
            "oos_mean_net_r": -2.059,
            "oos_trade_count": 6,
            "truth_certified": True,
            "optional_measurement": None,
            "selection_basis": "validation_mean_net_r",
        }
    }

    assert _result_metrics(trial) == {
        "oos_mean_net_r": -2.059,
        "oos_trade_count": 6,
        "truth_certified": True,
        "optional_measurement": None,
    }
    assert trial["metrics"]["selection_basis"] == "validation_mean_net_r"


def test_scientific_positive_publication_never_becomes_shadow_candidate() -> None:
    outcome, shadow_eligible = _publication_disposition(
        {"hypothesis_evaluation": {"outcome": "positive"}},
        {"shadow_eligible": True},
        passed=True,
    )

    assert outcome == "positive"
    assert shadow_eligible is False


def test_alpha_publication_rejects_missing_scientific_measurements() -> None:
    with pytest.raises(HTTPException, match="no scientific measurements"):
        _result_metrics({"metrics": {"selection_basis": "validation_mean_net_r"}})


def test_alpha_publication_uses_canonical_evidence_payload_digest() -> None:
    payload = {
        "kind": "run",
        "dataset_object_ids": ["11111111-1111-4111-8111-111111111111"],
        "specification_digest": "a" * 64,
        "code_digest": "b" * 64,
        "environment_digest": "c" * 64,
        "market_model_bundle_digest": "d" * 64,
        "representation_contract_digest": "e" * 64,
        "search_plan_digest": "f" * 64,
        "attempt": 1,
        "bundle_digest": "1" * 64,
        "bundle_manifest_digest": "2" * 64,
        "bundle_uri": f"bundle://sha256/{'1' * 64}",
    }

    evidence = _evidence(
        "22222222-2222-4222-8222-222222222222",
        "run",
        payload,
        "operational",
    )

    assert evidence.content_digest == canonical_payload_digest(
        evidence.payload.model_dump(mode="json")
    )


def test_alpha_publication_hashes_normalized_source_timestamp() -> None:
    payload = {
        "kind": "source",
        "title": "Admitted exchange panel",
        "origin": f"snapshot://sha256/{'a' * 64}",
        "rights": "internal research use",
        "acquired_at": "2026-04-30T23:59:00Z",
    }

    evidence = _evidence(
        "33333333-3333-4333-8333-333333333333",
        "source",
        payload,
        "primary",
    )

    normalized = evidence.payload.model_dump(mode="json")
    assert normalized["acquired_at"] == "2026-04-30T23:59:00Z"
    assert evidence.content_digest == canonical_payload_digest(normalized)


@pytest.mark.parametrize(
    "graph,retrieval,corpus",
    [
        (
            None,
            SimpleNamespace(source_epoch=7, corpus_digest="a" * 64),
            SimpleNamespace(epoch=7, corpus_digest="a" * 64),
        ),
        (
            SimpleNamespace(source_epoch=6),
            SimpleNamespace(source_epoch=7, corpus_digest="a" * 64),
            SimpleNamespace(epoch=7, corpus_digest="a" * 64),
        ),
        (
            SimpleNamespace(source_epoch=7),
            SimpleNamespace(source_epoch=6, corpus_digest="a" * 64),
            SimpleNamespace(epoch=7, corpus_digest="a" * 64),
        ),
        (
            SimpleNamespace(source_epoch=7),
            SimpleNamespace(source_epoch=7, corpus_digest="b" * 64),
            SimpleNamespace(epoch=7, corpus_digest="a" * 64),
        ),
    ],
)
def test_alpha_publication_fails_closed_for_missing_or_stale_projection(
    graph, retrieval, corpus
) -> None:
    with pytest.raises(HTTPException, match="stale"):
        _require_current_projections(graph, retrieval, corpus)
