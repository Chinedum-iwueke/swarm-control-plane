import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from app.schemas.research import BriefClaim, ResearchChunkCreate
from app.services.research import register_chunk, search_knowledge
from fastapi import HTTPException
from pydantic import ValidationError

ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def test_passage_contract_rejects_unknown_fields_and_bad_lines() -> None:
    with pytest.raises(ValidationError):
        ResearchChunkCreate(
            ordinal=0,
            section="Methods",
            line_start=4,
            line_end=3,
            text="A method passage.",
            text_digest="a" * 64,
            metadata={},
            command="curl example.test",
        )


def test_passage_digest_is_verified() -> None:
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=ID)
    payload = ResearchChunkCreate(
        ordinal=0,
        section="Methods",
        line_start=1,
        line_end=1,
        text="Immutable passage.",
        text_digest="0" * 64,
    )
    with pytest.raises(HTTPException, match="digest mismatch"):
        register_chunk(db, ID, payload)


def test_material_claim_requires_a_real_citation_shape() -> None:
    with pytest.raises(ValidationError, match="require citations"):
        BriefClaim(
            text="This is asserted as sourced.",
            evidence_class="source_passage",
            citation_chunk_ids=[],
        )
    with pytest.raises(ValidationError, match="masquerade"):
        BriefClaim(
            text="This is an inference.",
            evidence_class="agent_inference",
            citation_chunk_ids=[ID],
        )


def test_hybrid_search_combines_passage_and_section_terms_with_exact_citation() -> None:
    chunk = SimpleNamespace(
        id=ID,
        ordinal=3,
        section="Independent review",
        page=None,
        line_start=40,
        line_end=48,
        text="Negative results require independent review and durable retention.",
        text_digest=hashlib.sha256(b"passage").hexdigest(),
    )
    document = SimpleNamespace(
        document_key="m11-validation",
        title="M11 Validation",
        evidence_type="prior_result",
    )
    db = MagicMock()
    db.execute.return_value.all.return_value = [(chunk, document)]
    db.scalars.return_value.all.return_value = []
    result = search_knowledge(db, "independent negative review", 5, [])
    assert result["passages"][0]["document_key"] == "m11-validation"
    assert "lines 40-48" in result["passages"][0]["citation"]
    assert chunk.text_digest in result["passages"][0]["citation"]


def test_migration_makes_knowledge_records_append_only_and_indexes_text() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/d4e6f8a0b220_add_research_knowledge_foundation.py"
    ).read_text(encoding="utf-8")
    assert "to_tsvector('english', text)" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    for table in (
        "research_documents",
        "research_chunks",
        "research_retrieval_evaluations",
        "research_briefs",
    ):
        assert table in migration
