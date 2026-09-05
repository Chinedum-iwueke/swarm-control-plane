from __future__ import annotations

import uuid

import pytest

from hermes_mission_control.research_copilot import (
    CopilotClaim,
    CopilotDraft,
    CopilotError,
    CopilotQuestion,
    ResearchCopilot,
    _strict_schema,
)

OBJECT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


class FakeControlPlane:
    def __init__(self, *, abstained: bool = False) -> None:
        self.abstained = abstained
        self.context_requested = False

    async def research_retrieval(self, payload):
        return {
            "query": payload["query"],
            "projection_version": "hybrid-retrieval-v1.1.0",
            "corpus_digest": "a" * 64,
            "confidence": 0.86 if not self.abstained else 0.0,
            "abstained": self.abstained,
            "timings_ms": {"total": 12.5},
            "hits": [] if self.abstained else [{"object_id": str(OBJECT_ID)}],
        }

    async def research_context_pack(self, payload):
        self.context_requested = True
        return {
            "schema_version": "citation-context-pack-v1.0.0",
            "query": payload["query"],
            "purpose": payload["purpose"],
            "graph_query_digest": "b" * 64,
            "context_pack_digest": "c" * 64,
            "items": [
                {
                    "object_id": str(OBJECT_ID),
                    "object_type": "claim",
                    "content_digest": "d" * 64,
                    "access_class": "internal",
                    "excerpt": "Costs materially reduce short-horizon momentum.",
                    "citation": {
                        "replay_path": f"/v1/research/retrieval/objects/{OBJECT_ID}/replay",
                        "coordinates": {"page": 4, "line_start": 10, "line_end": 12},
                    },
                }
            ],
        }

    async def mathematics_search(self, payload):
        return {"items": [], "search_digest": "e" * 64}

    async def mathematics_context_pack(self, payload):
        raise AssertionError("No mathematics context should be requested without hits")


class FakeGenerator:
    def __init__(self, citation_id: uuid.UUID = OBJECT_ID) -> None:
        self.called = False
        self.citation_id = citation_id

    def generate(self, question, context_pack):
        self.called = True
        return CopilotDraft(
            answer="The corpus finds that costs reduce the signal.",
            confidence="supported",
            claims=[
                CopilotClaim(
                    text="Transaction costs reduce short-horizon momentum.",
                    evidence_class="source_evidence",
                    citation_object_ids=[self.citation_id],
                )
            ],
            limitations=["The cited evidence is market-specific."],
        )


@pytest.mark.asyncio
async def test_copilot_returns_digest_bound_cited_answer():
    control = FakeControlPlane()
    generator = FakeGenerator()
    answer = await ResearchCopilot(control, generator).ask(
        CopilotQuestion(question="Does momentum survive costs?")
    )
    assert answer["confidence"] == "supported"
    assert answer["context_pack_digest"] == "c" * 64
    assert answer["sources"][0]["object_id"] == str(OBJECT_ID)
    assert generator.called is True
    assert control.context_requested is True


@pytest.mark.asyncio
async def test_copilot_abstains_without_invoking_model():
    control = FakeControlPlane(abstained=True)
    generator = FakeGenerator()
    answer = await ResearchCopilot(control, generator).ask(
        CopilotQuestion(question="What evidence is unavailable?")
    )
    assert answer["confidence"] == "insufficient_evidence"
    assert answer["sources"] == []
    assert generator.called is False
    assert control.context_requested is False


@pytest.mark.asyncio
async def test_copilot_rejects_citation_outside_context_pack():
    control = FakeControlPlane()
    generator = FakeGenerator(uuid.UUID("22222222-2222-4222-8222-222222222222"))
    with pytest.raises(CopilotError, match="outside its context pack"):
        await ResearchCopilot(control, generator).ask(
            CopilotQuestion(question="Does momentum survive costs?")
        )


def test_codex_schema_requires_every_nested_property():
    schema = _strict_schema(CopilotDraft.model_json_schema())
    assert set(schema["required"]) == set(schema["properties"])
    claim_schema = schema["$defs"]["CopilotClaim"]
    assert set(claim_schema["required"]) == set(claim_schema["properties"])
