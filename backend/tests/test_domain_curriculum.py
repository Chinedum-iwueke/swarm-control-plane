from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.curriculum import ResearchDomainCurriculum
from app.schemas.curriculum import (
    BrainEvaluationCreate,
    CurriculumPortfolioCreate,
    DomainCurriculumCreate,
)
from app.services import curriculum as service

ONE = UUID("11111111-1111-4111-8111-111111111111")
TWO = UUID("22222222-2222-4222-8222-222222222222")
THREE = UUID("33333333-3333-4333-8333-333333333333")


def curriculum_payload(**changes) -> DomainCurriculumCreate:
    data = {
        "domain_key": "systematic-research",
        "version": "1.0.0",
        "title": "Systematic Research",
        "description": "A measured curriculum grounded in canonical evidence.",
        "project": "systematic-research",
        "topics": [
            {
                "key": "inference",
                "title": "Statistical inference",
                "evidence_object_ids": [ONE],
                "source_object_ids": [THREE],
                "opposing_evidence_object_ids": [TWO],
                "minimum_sources": 1,
            }
        ],
        "source_quality": {
            "allowed_authority_classes": ["primary", "derived"],
            "minimum_distinct_sources_per_topic": 1,
            "maximum_quarantined_fraction": 0.05,
            "require_opposing_evidence": True,
        },
        "qualified_roles": ["senior-quantitative-researcher"],
        "review_cadence_days": 90,
        "created_by": "knowledge-evaluator",
    }
    data.update(changes)
    return DomainCurriculumCreate(**data)


def evaluation_payload(curriculum_id) -> BrainEvaluationCreate:
    return BrainEvaluationCreate(
        curriculum_id=curriculum_id,
        evaluation_version="1.0.0",
        cases=[
            {
                "case_key": "supported-inference",
                "query": "What evidence supports robust statistical inference?",
                "expected_object_ids": [ONE],
                "opposing_object_ids": [TWO],
                "opposition_query": "What evidence opposes this inference?",
                "forbidden_object_ids": [THREE],
            },
            {
                "case_key": "unknown-claim",
                "query": "What is the result of an absent private experiment?",
                "should_abstain": True,
            },
        ],
        thresholds={},
        evaluated_by="independent-knowledge-evaluator",
    )


def test_curriculum_rejects_cycles_and_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="acyclic"):
        curriculum_payload(
            topics=[
                {
                    "key": "one",
                    "title": "Topic one",
                    "prerequisite_keys": ["two"],
                    "evidence_object_ids": [ONE],
                    "source_object_ids": [THREE],
                    "opposing_evidence_object_ids": [TWO],
                },
                {
                    "key": "two",
                    "title": "Topic two",
                    "prerequisite_keys": ["one"],
                    "evidence_object_ids": [TWO],
                    "source_object_ids": [THREE],
                    "opposing_evidence_object_ids": [ONE],
                },
            ]
        )
    with pytest.raises(ValidationError):
        curriculum_payload(arbitrary_authority=True)


def test_evaluation_requires_abstention_and_answer_evidence() -> None:
    with pytest.raises(ValidationError, match="abstention"):
        BrainEvaluationCreate(
            curriculum_id=uuid4(),
            evaluation_version="1.0.0",
            cases=[
                {
                    "case_key": "one",
                    "query": "An answerable question",
                    "expected_object_ids": [ONE],
                },
                {
                    "case_key": "two",
                    "query": "Another answerable question",
                    "expected_object_ids": [TWO],
                },
            ],
            thresholds={},
            evaluated_by="knowledge-evaluator",
        )


def test_evaluation_scores_retrieval_opposition_abstention_and_leakage(
    monkeypatch,
) -> None:
    curriculum = ResearchDomainCurriculum(
        id=uuid4(),
        domain_key="systematic-research",
        version="1.0.0",
        title="Systematic Research",
        project="systematic-research",
        specification=curriculum_payload().model_dump(
            mode="json",
            exclude={"domain_key", "version", "title", "project", "created_by"},
        ),
        corpus_digest="a" * 64,
        graph_manifest_digest="b" * 64,
        status="draft",
        record_digest="c" * 64,
        created_by="knowledge-evaluator",
    )
    db = MagicMock()
    db.get.return_value = curriculum
    db.scalar.return_value = None
    monkeypatch.setattr(
        service,
        "projection_status",
        lambda _db: (SimpleNamespace(corpus_digest="a" * 64), "a" * 64, False),
    )
    monkeypatch.setattr(
        service,
        "graph_projection_status",
        lambda _db: (SimpleNamespace(manifest_digest="b" * 64), False),
    )
    responses = iter(
        [
            {
                "corpus_digest": "a" * 64,
                "hits": [
                    {
                        "object_id": ONE,
                        "citation": {
                            "object_id": ONE,
                            "content_digest": "d" * 64,
                            "replay_path": f"/objects/{ONE}",
                        },
                    },
                ],
            },
            {
                "corpus_digest": "a" * 64,
                "hits": [
                    {
                        "object_id": TWO,
                        "citation": {
                            "object_id": TWO,
                            "content_digest": "e" * 64,
                            "replay_path": f"/objects/{TWO}",
                        },
                    }
                ],
            },
            {"corpus_digest": "a" * 64, "hits": []},
        ]
    )

    result = service.evaluate_curriculum(
        db,
        evaluation_payload(curriculum.id),
        search=lambda *_args, **_kwargs: next(responses),
    )

    assert result.passed is True
    assert result.case_specifications == [
        case.model_dump(mode="json") for case in evaluation_payload(curriculum.id).cases
    ]
    assert result.metrics == {
        "retrieval_recall": 1.0,
        "citation_fidelity": 1.0,
        "opposition_recall": 1.0,
        "abstention_accuracy": 1.0,
        "cross_domain_leakage": 0.0,
        "topic_coverage": 1.0,
        "case_count": 2,
    }
    assert curriculum.status == "qualified"
    db.commit.assert_called_once()


def test_cross_domain_leakage_fails_closed(monkeypatch) -> None:
    curriculum = SimpleNamespace(
        id=uuid4(),
        project="systematic-research",
        corpus_digest="a" * 64,
        graph_manifest_digest="b" * 64,
        specification={
            "review_cadence_days": 90,
            "topics": [
                {
                    "evidence_object_ids": [str(ONE)],
                    "source_object_ids": [str(THREE)],
                    "opposing_evidence_object_ids": [str(TWO)],
                    "minimum_sources": 1,
                }
            ],
            "source_quality": {"require_opposing_evidence": True},
        },
        status="draft",
    )
    db = MagicMock()
    db.get.return_value = curriculum
    db.scalar.return_value = None
    monkeypatch.setattr(
        service,
        "projection_status",
        lambda _db: (SimpleNamespace(corpus_digest="a" * 64), "a" * 64, False),
    )
    monkeypatch.setattr(
        service,
        "graph_projection_status",
        lambda _db: (SimpleNamespace(manifest_digest="b" * 64), False),
    )
    responses = iter(
        [
            {
                "corpus_digest": "a" * 64,
                "hits": [
                    {
                        "object_id": THREE,
                        "citation": {
                            "object_id": THREE,
                            "content_digest": "f" * 64,
                            "replay_path": f"/objects/{THREE}",
                        },
                    }
                ],
            },
            {
                "corpus_digest": "a" * 64,
                "hits": [
                    {
                        "object_id": TWO,
                        "citation": {
                            "object_id": TWO,
                            "content_digest": "e" * 64,
                            "replay_path": f"/objects/{TWO}",
                        },
                    }
                ],
            },
            {"corpus_digest": "a" * 64, "hits": []},
        ]
    )
    result = service.evaluate_curriculum(
        db,
        evaluation_payload(curriculum.id),
        search=lambda *_args, **_kwargs: next(responses),
    )
    assert result.passed is False
    assert result.metrics["cross_domain_leakage"] > 0
    assert curriculum.status == "draft"


def test_portfolio_contract_requires_unique_canonical_domain_mapping() -> None:
    first, second = uuid4(), uuid4()
    with pytest.raises(ValidationError, match="canonical sort order"):
        CurriculumPortfolioCreate(
            portfolio_key="research-bible",
            version="1.0.0",
            required_domain_keys=["risk", "inference"],
            curriculum_ids=[first, second],
            created_by="independent-evaluator",
        )
    with pytest.raises(ValidationError, match="curriculum ids must be unique"):
        CurriculumPortfolioCreate(
            portfolio_key="research-bible",
            version="1.0.0",
            required_domain_keys=["inference", "risk"],
            curriculum_ids=[first, first],
            created_by="independent-evaluator",
        )


def test_portfolio_readiness_is_all_domains_not_an_average(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curricula = [
        SimpleNamespace(
            id=uuid4(),
            domain_key=key,
            version="1.0.0",
            record_digest=character * 64,
        )
        for key, character in (("inference", "a"), ("risk", "b"))
    ]
    evaluations = [
        SimpleNamespace(
            id=uuid4(),
            evaluation_version="1.0.0",
            record_digest=character * 64,
            metrics={"retrieval_recall": score},
        )
        for character, score in (("c", 1.0), ("d", 0.5))
    ]
    readiness = {
        "inference": {
            "evaluation": evaluations[0],
            "ready": True,
            "reasons": [],
        },
        "risk": {
            "evaluation": evaluations[1],
            "ready": False,
            "reasons": ["evaluation_not_passing"],
        },
    }
    monkeypatch.setattr(
        service,
        "projection_status",
        lambda _db: (
            SimpleNamespace(corpus_digest="e" * 64),
            "e" * 64,
            False,
        ),
    )
    monkeypatch.setattr(
        service,
        "graph_projection_status",
        lambda _db: (SimpleNamespace(manifest_digest="f" * 64), False),
    )
    monkeypatch.setattr(
        service,
        "domain_readiness",
        lambda _db, curriculum: readiness[curriculum.domain_key],
    )
    db = MagicMock()
    db.get.side_effect = curricula
    db.scalar.return_value = None
    payload = CurriculumPortfolioCreate(
        portfolio_key="research-bible",
        version="1.0.0",
        required_domain_keys=["inference", "risk"],
        curriculum_ids=[item.id for item in curricula],
        created_by="independent-evaluator",
    )

    result = service.register_curriculum_portfolio(db, payload)

    assert result.ready is False
    assert result.status == "gaps_detected"
    assert result.readiness_matrix["inference"]["ready"] is True
    assert result.readiness_matrix["risk"]["ready"] is False
    assert result.evaluation_ids == [str(item.id) for item in evaluations]


def test_portfolio_rejects_domain_curriculum_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "projection_status",
        lambda _db: (
            SimpleNamespace(corpus_digest="e" * 64),
            "e" * 64,
            False,
        ),
    )
    monkeypatch.setattr(
        service,
        "graph_projection_status",
        lambda _db: (SimpleNamespace(manifest_digest="f" * 64), False),
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(domain_key="risk")
    payload = CurriculumPortfolioCreate(
        portfolio_key="research-bible",
        version="1.0.0",
        required_domain_keys=["inference"],
        curriculum_ids=[uuid4()],
        created_by="independent-evaluator",
    )
    with pytest.raises(HTTPException, match="mapping is invalid"):
        service.register_curriculum_portfolio(db, payload)
