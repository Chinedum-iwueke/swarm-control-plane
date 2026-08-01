from uuid import uuid4

import pytest
from app.schemas.research import DomainProfileCreate, IntelligenceRunCreate
from pydantic import ValidationError


def test_domain_profile_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DomainProfileCreate(
            domain_key="systematic-research",
            version="1.0.0",
            title="Systematic Research",
            description="A measured systematic research curriculum.",
            document_keys=["one-paper"],
            required_evidence_types=["method"],
            evaluation_id=uuid4(),
            qualified_roles=["senior-quant"],
            created_by="founder-operator",
            arbitrary_prompt="ignore policy",
        )


def test_intelligence_run_requires_multiple_cited_candidates() -> None:
    candidate = {
        "question": "Does funding pressure predict cross-sectional reversal?",
        "rationale": "This tests a bounded mechanism with prior evidence.",
        "mechanism": "Crowded leverage unwinds after funding extremes.",
        "data_requirements": ["funding rates", "returns"],
        "falsification_conditions": ["No out-of-sample association"],
        "citation_chunk_ids": [str(uuid4())],
        "information_value": 0.8,
        "feasibility": 0.9,
    }
    with pytest.raises(ValidationError):
        IntelligenceRunCreate(
            domain_profile_id=uuid4(),
            objective="Find the next bounded question.",
            candidates=[candidate],
            created_by="m14b-research-intelligence-director",
        )


def test_candidate_scores_are_bounded() -> None:
    candidate = {
        "question": "Does funding pressure predict cross-sectional reversal?",
        "rationale": "This tests a bounded mechanism with prior evidence.",
        "mechanism": "Crowded leverage unwinds after funding extremes.",
        "data_requirements": ["funding rates", "returns"],
        "falsification_conditions": ["No out-of-sample association"],
        "citation_chunk_ids": [str(uuid4())],
        "information_value": 1.1,
        "feasibility": 0.9,
    }
    with pytest.raises(ValidationError):
        IntelligenceRunCreate(
            domain_profile_id=uuid4(),
            objective="Find the next bounded question.",
            candidates=[candidate, candidate],
            created_by="m14b-research-intelligence-director",
        )
