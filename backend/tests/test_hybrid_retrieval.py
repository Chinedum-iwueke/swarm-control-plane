from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.clients.retrieval import CanonicalRetrievalClient, RetrievalClientError
from app.schemas.retrieval import HybridRetrievalRequest
from app.services.evidence import EvidenceAccessContext
from app.services.retrieval import (
    PROJECTION_VERSION,
    _authorized_projections,
    build_projections,
    fuse_rankings,
    hashed_vector,
    hybrid_search,
    projection_status,
    score_channels,
    term_frequencies,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures/retrieval"
PROJECT = "systematic-research"
SCHEMA = "canonical-evidence-v1.0.0"


def projection(
    object_id: str,
    scientific_type: str,
    text: str,
    *,
    neighbors: list[str] | None = None,
    access_class: str = "internal",
    schema: str = SCHEMA,
):
    terms = term_frequencies(text)
    return SimpleNamespace(
        object_id=UUID(object_id),
        project=PROJECT,
        access_class=access_class,
        object_schema_version=schema,
        scientific_type=scientific_type,
        content_digest=(object_id[0] * 64),
        content_text=text,
        aliases=[f"fixture:{scientific_type}:{object_id}"],
        lexical_terms=terms,
        vector=hashed_vector(terms),
        graph_neighbors=[UUID(item) for item in (neighbors or [])],
    )


def golden_corpus() -> list:
    return [
        projection(
            "11111111-1111-4111-8111-111111111111",
            "section",
            "Transaction Cost Adjusted Momentum",
            neighbors=["22222222-2222-4222-8222-222222222222"],
        ),
        projection(
            "22222222-2222-4222-8222-222222222222",
            "paragraph",
            "Short horizon momentum loses predictive value after transaction costs.",
            neighbors=[
                "11111111-1111-4111-8111-111111111111",
                "33333333-3333-4333-8333-333333333333",
            ],
        ),
        projection(
            "33333333-3333-4333-8333-333333333333",
            "equation",
            "net_return = gross_return - transaction_cost",
            neighbors=["22222222-2222-4222-8222-222222222222"],
        ),
        projection(
            "44444444-4444-4444-8444-444444444444",
            "table",
            "regime sharpe drawdown weekend 0.4 0.2",
        ),
        projection(
            "55555555-5555-4555-8555-555555555555",
            "figure",
            "Figure 2 volatility regime performance",
        ),
        projection(
            "66666666-6666-4666-8666-666666666666",
            "citation",
            "doi: 10.1000/momentum.2026 source citation",
        ),
    ]


def ranked(query: str) -> list[UUID]:
    scores = score_channels(golden_corpus(), query)
    return [
        item[0]
        for item in fuse_rankings(
            scores, ["exact", "lexical", "vector", "graph"], 10
        )
    ]


def test_versioned_golden_relevance_meets_declared_thresholds() -> None:
    fixture = json.loads(
        (FIXTURE_ROOT / "golden-evaluation-v1.json").read_text(encoding="utf-8")
    )
    reciprocal_ranks = []
    recalled = 0
    by_id = {str(item.object_id): item for item in golden_corpus()}
    for case in fixture["cases"]:
        results = ranked(case["query"])
        expected = UUID(case["expected_object_id"])
        rank = results.index(expected) + 1
        reciprocal_ranks.append(1 / rank)
        recalled += int(expected in results[:3])
        assert by_id[str(expected)].scientific_type == case["expected_type"]
    assert sum(reciprocal_ranks) / len(reciprocal_ranks) >= fixture["minimum_mrr"]
    assert recalled / len(reciprocal_ranks) >= fixture["minimum_recall_at_3"]


def test_exact_identity_and_graph_assisted_channels_are_explainable() -> None:
    corpus = golden_corpus()
    target = corpus[1]
    scores = score_channels(corpus, str(target.object_id))
    assert scores["exact"][target.object_id] == 1.0
    assert corpus[0].object_id in scores["graph"]


def test_vector_channel_adds_declared_synonym_recall() -> None:
    scores = score_channels(golden_corpus(), "trend following fees")
    paragraph_id = UUID("22222222-2222-4222-8222-222222222222")
    assert paragraph_id not in scores["lexical"]
    assert scores["vector"][paragraph_id] > 0


def test_equation_identifiers_match_natural_language_terms() -> None:
    scores = score_channels(golden_corpus(), "net return transaction cost")
    equation_id = UUID("33333333-3333-4333-8333-333333333333")
    assert scores["lexical"][equation_id] > 0


def test_rrf_ties_are_deterministic_by_object_id() -> None:
    first = UUID("11111111-1111-4111-8111-111111111111")
    second = UUID("22222222-2222-4222-8222-222222222222")
    scores = {
        "exact": {second: 1.0, first: 1.0},
        "lexical": {},
        "vector": {},
        "graph": {},
    }
    assert [item[0] for item in fuse_rankings(scores, ["exact"], 2)] == [
        first,
        second,
    ]


def test_request_rejects_duplicate_channels_and_invalid_compatibility() -> None:
    with pytest.raises(ValidationError, match="channels must be unique"):
        HybridRetrievalRequest(query="momentum", channels=["exact", "exact"])
    with pytest.raises(ValidationError, match="schema versions are invalid"):
        HybridRetrievalRequest(
            query="momentum", compatible_schema_versions=["anything"]
        )


def test_project_access_is_denied_before_projection_query() -> None:
    access = EvidenceAccessContext(
        actor="reader",
        projects=frozenset({"allowed-project"}),
        max_access_class="internal",
    )
    with pytest.raises(HTTPException) as error:
        _authorized_projections(
            MagicMock(),
            HybridRetrievalRequest(query="momentum", project=PROJECT),
            access,
        )
    assert error.value.status_code == 403


def test_access_and_compatibility_filters_are_applied_to_database_query() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    access = EvidenceAccessContext(
        actor="reader",
        projects=frozenset({PROJECT}),
        max_access_class="internal",
    )
    _authorized_projections(
        db,
        HybridRetrievalRequest(
            query="momentum",
            project=PROJECT,
            compatible_schema_versions=[SCHEMA],
            scientific_types=["table"],
        ),
        access,
    )
    statement = db.scalars.call_args.args[0]
    parameters = statement.compile().params
    flattened = repr(parameters)
    assert "protected" not in flattened
    assert PROJECT in flattened
    assert SCHEMA in flattened
    assert "table" in flattened


def test_stale_projection_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    state = SimpleNamespace(
        projection_version=PROJECTION_VERSION,
        corpus_digest="1" * 64,
    )
    monkeypatch.setattr(
        "app.services.retrieval.projection_status",
        lambda db: (state, "2" * 64, True),
    )
    with pytest.raises(HTTPException, match="stale") as error:
        hybrid_search(
            MagicMock(),
            HybridRetrievalRequest(query="momentum"),
            EvidenceAccessContext(
                actor="reader",
                projects=frozenset({PROJECT}),
                max_access_class="internal",
            ),
        )
    assert error.value.status_code == 409


def test_projection_status_detects_digest_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(corpus_digest="1" * 64)
    db = MagicMock()
    db.get.return_value = state
    monkeypatch.setattr("app.services.retrieval.corpus_digest", lambda db: "2" * 64)
    assert projection_status(db) == (state, "2" * 64, True)


def test_projection_rebuild_is_atomic_and_digest_bound() -> None:
    object_id = UUID("22222222-2222-4222-8222-222222222222")
    canonical = SimpleNamespace(
        id=object_id,
        project=PROJECT,
        access_class="internal",
        object_schema_version=SCHEMA,
        content_digest="2" * 64,
        payload={
            "scientific_type": "paragraph",
            "content_text": "Momentum after transaction costs",
        },
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [canonical]

    def result(rows):
        value = MagicMock()
        value.all.return_value = rows
        return value

    db.execute.side_effect = [
        result([]),
        result([(object_id, "fixture", "paragraph", "native-2")]),
        result(
            [
                SimpleNamespace(
                    id=object_id,
                    content_digest="2" * 64,
                    object_schema_version=SCHEMA,
                    project=PROJECT,
                    access_class="internal",
                )
            ]
        ),
        result([]),
        result(
            [
                SimpleNamespace(
                    canonical_object_id=object_id,
                    namespace="fixture",
                    native_object_type="paragraph",
                    alias_value="native-2",
                )
            ]
        ),
        MagicMock(),
        MagicMock(),
    ]
    state = build_projections(db)
    added = [call.args[0] for call in db.add.call_args_list]
    projection_record = added[0]
    assert projection_record.object_id == object_id
    assert projection_record.aliases == [
        "fixture:paragraph:native-2",
        "native-2",
    ]
    assert projection_record.vector == hashed_vector(
        term_frequencies("Momentum after transaction costs")
    )
    assert state.corpus_digest == (
        "3fcd6f4b2b54f059928145dd1c27cf4b779a388c101e5e9079f1c9cf88c20f7d"
    )
    assert db.commit.call_count == 1


def test_result_is_reauthorized_against_canonical_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = golden_corpus()[1]
    state = SimpleNamespace(
        projection_version=PROJECTION_VERSION,
        corpus_digest="a" * 64,
    )
    canonical = SimpleNamespace(
        content_digest=item.content_digest,
        payload={"coordinates": {"page": 2, "line_start": 10, "line_end": 11}},
    )
    monkeypatch.setattr(
        "app.services.retrieval.projection_status",
        lambda db: (state, "a" * 64, False),
    )
    monkeypatch.setattr(
        "app.services.retrieval._authorized_projections",
        lambda db, request, access: [item],
    )
    canonical_fetch = MagicMock(return_value=canonical)
    monkeypatch.setattr(
        "app.services.retrieval.get_evidence_object", canonical_fetch
    )
    response = hybrid_search(
        MagicMock(),
        HybridRetrievalRequest(query="momentum"),
        EvidenceAccessContext(
            actor="reader",
            projects=frozenset({PROJECT}),
            max_access_class="internal",
        ),
    )
    assert response["hits"][0]["citation"]["coordinates"] == canonical.payload[
        "coordinates"
    ]
    assert response["hits"][0]["citation"]["replay_path"].endswith("/replay")
    assert canonical_fetch.call_args.kwargs == {"audit": False}


def test_projection_digest_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = golden_corpus()[1]
    state = SimpleNamespace(
        projection_version=PROJECTION_VERSION,
        corpus_digest="a" * 64,
    )
    monkeypatch.setattr(
        "app.services.retrieval.projection_status",
        lambda db: (state, "a" * 64, False),
    )
    monkeypatch.setattr(
        "app.services.retrieval._authorized_projections",
        lambda db, request, access: [item],
    )
    monkeypatch.setattr(
        "app.services.retrieval.get_evidence_object",
        lambda *args, **kwargs: SimpleNamespace(
            content_digest="f" * 64,
            payload={"coordinates": {"page": 1, "line_start": 1, "line_end": 1}},
        ),
    )
    with pytest.raises(HTTPException, match="no longer matches"):
        hybrid_search(
            MagicMock(),
            HybridRetrievalRequest(query="momentum"),
            EvidenceAccessContext(
                actor="reader",
                projects=frozenset({PROJECT}),
                max_access_class="internal",
            ),
        )


@pytest.mark.asyncio
async def test_typed_client_sends_bearer_and_parses_search() -> None:
    token = "secret-retrieval-token-value"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {token}"
        return httpx.Response(
            200,
            json={
                "query": "momentum",
                "projection_version": PROJECTION_VERSION,
                "corpus_digest": "a" * 64,
                "fusion": "rrf-v1",
                "stale": False,
                "hits": [],
            },
        )

    async with CanonicalRetrievalClient(
        "http://control-plane",
        token,
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await client.search(HybridRetrievalRequest(query="momentum"))
    assert result.corpus_digest == "a" * 64


@pytest.mark.asyncio
async def test_typed_client_redacts_token_from_errors() -> None:
    token = "secret-retrieval-token-value"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": f"failure {token}"})

    async with CanonicalRetrievalClient(
        "http://control-plane",
        token,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(RetrievalClientError) as error:
            await client.status()
    assert token not in str(error.value)
    assert "[REDACTED]" in str(error.value)


def test_openapi_exposes_authenticated_retrieval_surface() -> None:
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
        for method in methods:
            assert paths[path][method]["security"] == [
                {fixture["security_scheme"]: []}
            ]
    schema = document["components"]["schemas"][fixture["schema"]]
    assert sorted(schema["required"]) == fixture["required_fields"]


def test_migration_owns_only_rebuildable_projection_tables() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/e7a1c4d83b20_add_hybrid_retrieval.py"
    ).read_text(encoding="utf-8")
    assert "evidence_retrieval_projections" in migration
    assert "evidence_retrieval_states" in migration
    assert 'down_revision: str | None = "d6f9b2e53a70"' in migration
    assert "canonical_evidence_objects" in migration
    assert '"canonical_identity_aliases"' in migration
    assert 'server_default=sa.text("now()")' in migration
