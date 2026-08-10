from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import httpx
import pytest
from app.clients.memory import InstitutionalMemoryClient, MemoryClientError
from app.schemas.memory import (
    BeliefAssessment,
    BeliefLedgerCreate,
    DossierCompileCreate,
    EpisodePublishCreate,
    OppositionCreate,
    OppositionReviewCreate,
    OutcomeCreate,
)
from app.services.evidence import EvidenceAccessContext
from app.services.memory import (
    compile_dossier,
    create_opposition,
    publish_belief,
    publish_episode,
    replay_dossier,
    review_opposition,
    search_outcomes,
)
from fastapi import HTTPException
from pydantic import ValidationError

FIXTURE_ROOT = Path(__file__).parent / "fixtures/memory"
NOW = datetime(2026, 8, 10, tzinfo=UTC)
PROJECT = "systematic-research"
CLAIM_ID = UUID("11111111-1111-4111-8111-111111111111")
SUPPORT_ID = UUID("22222222-2222-4222-8222-222222222222")
OPPOSE_ID = UUID("33333333-3333-4333-8333-333333333333")
BELIEF_ID = UUID("44444444-4444-4444-8444-444444444444")


def access(maximum: str = "internal", projects: frozenset[str] | None = None):
    return EvidenceAccessContext(
        actor="knowledge-reviewer",
        projects=projects or frozenset({PROJECT}),
        max_access_class=maximum,
        may_write=True,
    )


def canonical(
    object_id: UUID,
    object_type: str,
    *,
    access_class: str = "internal",
    digest: str | None = None,
    supersedes_object_id: UUID | None = None,
):
    return SimpleNamespace(
        id=object_id,
        object_type=object_type,
        project=PROJECT,
        access_class=access_class,
        content_version="1",
        content_digest=digest or str(object_id).replace("-", "") * 2,
        payload={"kind": object_type, "coordinates": {"page": 1, "line_start": 2, "line_end": 3}},
        supersedes_object_id=supersedes_object_id,
    )


def opposition_payload() -> OppositionCreate:
    return OppositionCreate(
        project=PROJECT,
        subject_claim_id=CLAIM_ID,
        opposing_object_id=OPPOSE_ID,
        opposition_type="direct_contradiction",
        comparability={
            "population": "BTC hourly bars",
            "horizon": "one hour",
            "method": "prospective replication",
            "materially_comparable": True,
            "unresolved_differences": [],
        },
        rationale="The replication estimates the opposite signed effect.",
        recorded_by="canon-curator",
    )


def belief_payload(**updates) -> BeliefLedgerCreate:
    document = {
        "object_id": BELIEF_ID,
        "content_version": "1",
        "project": PROJECT,
        "access_class": "internal",
        "claim_object_id": CLAIM_ID,
        "scope": "BTC hourly observations under declared transaction costs",
        "assessment": {
            "kind": "qualitative",
            "value": "weakened",
            "population": "BTC hourly bars",
            "horizon": "one hour",
        },
        "supporting_evidence_ids": [SUPPORT_ID],
        "opposing_evidence_ids": [OPPOSE_ID],
        "synthesis_method": "Independent evidence-weighted review",
        "uncertainty": [
            {
                "source": "sampling",
                "representation": "interval",
                "detail": "The interval overlaps economically small effects.",
            }
        ],
        "dependencies": [],
        "owner": "canon-curator",
        "reviewers": ["governance-reviewer"],
        "minority_assessments": [],
        "valid_from": NOW,
        "review_due": NOW + timedelta(days=30),
        "invalidation_conditions": ["source artifact is invalidated"],
        "created_by": "canon-curator",
    }
    document.update(updates)
    return BeliefLedgerCreate.model_validate(document)


def dossier_payload() -> DossierCompileCreate:
    return DossierCompileCreate(
        dossier_key="RI004-PILOT",
        version="1.0.0",
        project=PROJECT,
        access_class="internal",
        question="Does short-horizon momentum survive transaction costs?",
        decision_context="Determine whether another bounded replication is justified.",
        scope="BTC hourly evidence available before the cutoff.",
        evidence_cutoff=NOW,
        claim_ids=[CLAIM_ID],
        supporting_evidence_ids=[SUPPORT_ID],
        opposing_evidence_ids=[OPPOSE_ID],
        belief_ids=[],
        opposition_record_ids=[],
        outcome_record_ids=[],
        episode_ids=[],
        retrieval_manifest={"projection_version": "hybrid-retrieval-v1.0.0"},
        doctrine_and_authority=["B3-KR10", "B3-KR11", "B3-KR15"],
        unknowns=["No independent second market replication."],
        risks=["Single-market dependence."],
        dissent=["Minority reviewer favors one additional trial."],
        synthesis="The positive result is opposed by a comparable negative replication.",
        recommendation="Retain as disputed; do not promote.",
        compiler_version="evidence-dossier-v1.0.0",
        compiled_by="canon-curator",
        expires_at=NOW + timedelta(days=30),
    )


def test_direct_contradiction_requires_material_comparability() -> None:
    with pytest.raises(ValidationError, match="must be comparable"):
        opposition_payload().model_copy(
            update={
                "comparability": opposition_payload().comparability.model_copy(
                    update={"materially_comparable": False}
                )
            }
        ).model_dump()
        OppositionCreate.model_validate(
            opposition_payload().model_dump()
            | {
                "comparability": opposition_payload().comparability.model_dump()
                | {"materially_comparable": False}
            }
        )


def test_opposition_is_proposed_and_review_creates_superseding_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = canonical(CLAIM_ID, "claim")
    opposing = canonical(OPPOSE_ID, "scientific_object")
    values = iter([claim, opposing])
    monkeypatch.setattr(
        "app.services.memory.get_evidence_object",
        lambda *args, **kwargs: next(values),
    )
    db = MagicMock()
    proposed = create_opposition(db, opposition_payload(), access())
    assert proposed.status == "proposed"
    assert proposed.supersedes_id is None

    proposed.id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    db.get.return_value = proposed
    db.scalar.return_value = None
    monkeypatch.setattr(
        "app.services.memory.get_evidence_object", lambda *args, **kwargs: claim
    )
    reviewed = review_opposition(
        db,
        proposed.id,
        OppositionReviewCreate(
            status="unresolved",
            resolution="Both estimates remain credible pending another replication.",
            reviewed_by="independent-reviewer",
        ),
        access(),
    )
    assert reviewed.supersedes_id == proposed.id
    assert reviewed.status == "unresolved"
    assert proposed.status == "proposed"


def test_opposition_cannot_be_reviewed_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    previous = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        status="proposed",
        supersedes_id=None,
        subject_claim_id=CLAIM_ID,
    )
    db = MagicMock()
    db.get.return_value = previous
    db.scalar.return_value = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    monkeypatch.setattr(
        "app.services.memory.get_evidence_object",
        lambda *args, **kwargs: canonical(CLAIM_ID, "claim"),
    )
    with pytest.raises(HTTPException, match="Only a proposed") as error:
        review_opposition(
            db,
            previous.id,
            OppositionReviewCreate(
                status="reviewed",
                resolution="A prior reviewer already handled this exact record.",
                reviewed_by="independent-reviewer",
            ),
            access(),
        )
    assert error.value.status_code == 409


def test_invalid_attempt_cannot_masquerade_as_valid_negative() -> None:
    base = {
        "project": PROJECT,
        "evidence_object_id": SUPPORT_ID,
        "outcome_kind": "invalid_attempt",
        "question": "Does momentum survive costs?",
        "scope": {
            "population": "BTC",
            "horizon": "one hour",
            "environment": "rehearsal",
            "limitations": [],
        },
        "method": "Prospective test",
        "uncertainty": [
            {"source": "implementation", "representation": "unknown", "detail": "Run failed."}
        ],
        "failure_mechanisms": [],
        "affected_claim_ids": [],
        "recorded_by": "research-runner",
    }
    with pytest.raises(ValidationError, match="failure mechanism"):
        OutcomeCreate.model_validate(base)


def test_negative_result_recall_keeps_invalid_attempts_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        outcome_kind="valid_negative",
        evidence_object_id=SUPPORT_ID,
        question="Momentum does not survive transaction costs",
        method="prospective replication",
        failure_mechanisms=[],
        scope={"limitations": ["single market"]},
        created_at=NOW,
    )
    invalid = SimpleNamespace(
        id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        outcome_kind="invalid_attempt",
        evidence_object_id=OPPOSE_ID,
        question="Momentum transaction cost test",
        method="failed parser run",
        failure_mechanisms=["corrupt input"],
        scope={"limitations": []},
        created_at=NOW,
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [valid, invalid]
    monkeypatch.setattr(
        "app.services.memory.get_evidence_object",
        lambda *args, **kwargs: canonical(SUPPORT_ID, "run"),
    )
    result = search_outcomes(db, "momentum transaction costs", PROJECT, access())
    assert result["valid_negative"] == [valid]
    assert result["invalid_attempt"] == [invalid]


def test_probabilistic_belief_requires_event_and_calibration_basis() -> None:
    with pytest.raises(ValidationError, match="event and calibration basis"):
        BeliefAssessment(
            kind="probabilistic",
            value="0.60",
            population="BTC",
            horizon="one hour",
        )


def test_belief_revision_is_canonical_and_preserves_supersession(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_id = UUID("55555555-5555-4555-8555-555555555555")
    captured = MagicMock()
    monkeypatch.setattr("app.services.memory.register_evidence_object", captured)
    payload = belief_payload(
        object_id=UUID("66666666-6666-4666-8666-666666666666"),
        content_version="2",
        supersedes_object_id=previous_id,
    )
    publish_belief(MagicMock(), payload, access())
    envelope = captured.call_args.args[1]
    assert envelope.object_type == "belief"
    assert envelope.supersedes_object_id == previous_id
    assert envelope.payload.assessment_type == "qualitative"
    assert envelope.payload.confidence is None
    assert envelope.payload.opposing_evidence_ids == [OPPOSE_ID]


def test_episode_publication_preserves_lineage_without_approval_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = MagicMock()
    monkeypatch.setattr("app.services.memory.register_evidence_object", captured)
    payload = EpisodePublishCreate(
        object_id=UUID("77777777-7777-4777-8777-777777777777"),
        content_version="1",
        project=PROJECT,
        access_class="internal",
        question="Why did the prospective momentum replication fail?",
        prior_belief_object_id=BELIEF_ID,
        input_object_ids=[CLAIM_ID],
        output_object_ids=[SUPPORT_ID],
        decision_object_ids=[OPPOSE_ID],
        tools=["bulletproof-bt"],
        failures=["cost-stress threshold missed"],
        alternatives=["liquidity-regime interaction"],
        surprise="The cost sensitivity was materially larger than expected.",
        lessons=["Pre-register a broader cost grid."],
        new_questions=["Is the effect conditional on weekend liquidity?"],
        created_by="research-runner",
    )
    publish_episode(MagicMock(), payload, access())
    envelope = captured.call_args.args[1]
    document = envelope.payload.model_dump(mode="json")
    assert envelope.object_type == "episode"
    assert document["prior_belief_object_id"] == str(BELIEF_ID)
    assert document["input_object_ids"] == [str(CLAIM_ID)]
    assert document["output_object_ids"] == [str(SUPPORT_ID)]
    assert "approval" not in document


def test_conflicting_editions_remain_distinct_in_frozen_dossier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = canonical(CLAIM_ID, "claim")
    first_edition = canonical(SUPPORT_ID, "scientific_object", digest="a" * 64)
    revised_edition = canonical(OPPOSE_ID, "scientific_object", digest="b" * 64)
    records = {
        item.id: item for item in (claim, first_edition, revised_edition)
    }
    db = MagicMock()
    db.get.side_effect = lambda model, object_id: records.get(object_id)
    db.scalars.return_value.all.return_value = [claim]
    monkeypatch.setattr(
        "app.services.memory.get_evidence_object",
        lambda db, object_id, context, audit=False: records[object_id],
    )
    dossier = compile_dossier(db, dossier_payload(), access())
    objects = dossier.dossier["objects"]
    assert objects["supporting_evidence"][0]["content_digest"] == "a" * 64
    assert objects["opposing_evidence"][0]["content_digest"] == "b" * 64
    assert objects["supporting_evidence"][0]["object_id"] != (
        objects["opposing_evidence"][0]["object_id"]
    )


def test_dossier_freezes_exact_digests_and_redacts_protected_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = canonical(CLAIM_ID, "claim")
    support = canonical(SUPPORT_ID, "scientific_object")
    protected = canonical(OPPOSE_ID, "scientific_object", access_class="protected")
    records = {item.id: item for item in (claim, support, protected)}
    db = MagicMock()
    db.get.side_effect = lambda model, object_id: records.get(object_id)
    db.scalars.return_value.all.return_value = [claim]

    def authorize(db, object_id, context, audit=False):
        record = records[object_id]
        if record.access_class == "protected" and context.max_access_class != "protected":
            raise HTTPException(status_code=403, detail="denied")
        return record

    monkeypatch.setattr("app.services.memory.get_evidence_object", authorize)
    dossier = compile_dossier(db, dossier_payload(), access("protected"))
    objects = dossier.dossier["objects"]
    assert objects["claims"][0]["content_digest"] == claim.content_digest
    assert objects["supporting_evidence"][0]["coordinates"]["page"] == 1
    assert objects["opposing_evidence"] == [
        {
            "object_id": str(OPPOSE_ID),
            "access": "redacted",
            "reason": "access_class_denied",
        }
    ]
    assert dossier.dossier["access_limitations"] == objects["opposing_evidence"]
    assert objects["supporting_evidence"][0]["citation_replay_path"] == (
        f"/v1/research/retrieval/objects/{SUPPORT_ID}/replay"
    )


def test_dossier_replay_reports_supersession_without_mutation() -> None:
    object_id = SUPPORT_ID
    frozen = {
        "object_id": str(object_id),
        "object_type": "scientific_object",
        "content_version": "1",
        "content_digest": "2" * 64,
        "access": "included",
        "coordinates": {"page": 1, "line_start": 2, "line_end": 3},
    }
    dossier = SimpleNamespace(
        id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        project=PROJECT,
        access_class="internal",
        dossier={"objects": {"supporting_evidence": [frozen]}},
    )
    current = canonical(object_id, "scientific_object", digest="2" * 64)
    db = MagicMock()
    db.get.side_effect = [dossier, current]
    db.scalar.return_value = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    replayed, exact, impacts = replay_dossier(db, dossier.id, access())
    assert replayed.dossier == dossier.dossier
    assert exact is False
    assert impacts == [
        {
            "group": "supporting_evidence",
            "object_id": str(object_id),
            "impact": "superseded",
        }
    ]


def test_cross_role_dossier_access_is_denied() -> None:
    dossier = SimpleNamespace(
        project=PROJECT,
        access_class="restricted",
    )
    db = MagicMock()
    db.get.return_value = dossier
    with pytest.raises(HTTPException) as error:
        replay_dossier(db, UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"), access("internal"))
    assert error.value.status_code == 403


def test_dossier_compiler_cannot_escalate_its_access_class() -> None:
    payload = dossier_payload().model_copy(update={"access_class": "protected"})
    with pytest.raises(HTTPException, match="exceeds compiler access") as error:
        compile_dossier(MagicMock(), payload, access("internal"))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_memory_client_parses_frozen_dossiers_and_redacts_token() -> None:
    token = "memory-client-secret-token"
    dossier_id = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {token}"
        return httpx.Response(500, json={"detail": f"failure {token}"})

    async with InstitutionalMemoryClient(
        "http://control-plane", token, transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(MemoryClientError) as error:
            await client.get_dossier(dossier_id)
    assert token not in str(error.value)
    assert "[REDACTED]" in str(error.value)


def test_openapi_exposes_authenticated_immutable_memory_surface() -> None:
    from app.main import app

    fixture = json.loads(
        (FIXTURE_ROOT / "openapi-surface-v1.json").read_text(encoding="utf-8")
    )
    document = app.openapi()
    paths = document["paths"]
    assert {path: sorted(paths[path]) for path in fixture["routes"]} == fixture[
        "routes"
    ]
    for path, methods in fixture["routes"].items():
        assert "put" not in methods and "delete" not in methods and "patch" not in methods
        for method in methods:
            assert paths[path][method]["security"] == [
                {fixture["security_scheme"]: []}
            ]


def test_migration_is_additive_and_bound_to_ri003() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/f9b2d5e74c10_add_institutional_memory.py"
    ).read_text(encoding="utf-8")
    for table in (
        "evidence_opposition_records",
        "evidence_outcome_records",
        "evidence_dossiers",
    ):
        assert table in migration
    assert 'down_revision: str | None = "e7a1c4d83b20"' in migration
