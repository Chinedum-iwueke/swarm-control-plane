from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from app.schemas.graph import (
    CanonicalEdgeCreate,
    CognitiveToolRequest,
    GraphQueryRequest,
    GraphQueryResponse,
)
from app.services.evidence import EvidenceAccessContext
from app.services.graph import (
    _active,
    _adjacency,
    _authorized_edges,
    _decode_graph_cursor,
    _edge_response,
    _encode_graph_cursor,
    _frontier_edges,
    _node_response,
    _stream_digest,
    _traverse,
    _validate_edge_types,
    calculate,
    digest_document,
    execute_cognitive_tool,
    graph_projection_status,
    query_graph,
)
from fastapi import HTTPException
from pydantic import ValidationError

ONE = UUID("11111111-1111-4111-8111-111111111111")
TWO = UUID("22222222-2222-4222-8222-222222222222")
THREE = UUID("33333333-3333-4333-8333-333333333333")


def test_stream_digest_reports_prepare_progress(monkeypatch) -> None:
    monkeypatch.setattr("app.services.graph._PROJECTION_BATCH_SIZE", 2)
    updates = []

    digest = _stream_digest(
        [("version", "v1"), ("object", "one"), ("object", "two")],
        progress=lambda *update: updates.append(update),
        total=3,
    )

    assert len(digest) == 64
    assert updates == [
        ("digest-corpus", 2, 3, "records"),
        ("digest-corpus", 3, 3, "records"),
    ]


def edge(source: UUID, target: UUID, **kwargs):
    return SimpleNamespace(
        subject_id=source,
        object_id=target,
        predicate=kwargs.get("predicate", "supports"),
        valid_from=kwargs.get("valid_from"),
        valid_until=kwargs.get("valid_until"),
    )


def test_edge_contract_rejects_self_reference_and_invalid_interval() -> None:
    base = {
        "subject_id": ONE,
        "predicate": "supports",
        "object_id": TWO,
        "provenance_object_id": THREE,
        "access_class": "internal",
        "created_by": "canon-curator",
    }
    CanonicalEdgeCreate(**base)
    with pytest.raises(ValidationError, match="self-referential"):
        CanonicalEdgeCreate(**{**base, "object_id": ONE})
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="valid_until"):
        CanonicalEdgeCreate(
            **{**base, "valid_from": now, "valid_until": now - timedelta(seconds=1)}
        )


def test_edge_vocabulary_enforces_scientific_direction() -> None:
    _validate_edge_types("supports", "scientific_object", "claim")
    with pytest.raises(HTTPException, match="invalid"):
        _validate_edge_types("supports", "claim", "scientific_object")


def test_temporal_semantics_use_half_open_validity_interval() -> None:
    now = datetime.now(UTC)
    assert _active(edge(ONE, TWO, valid_from=now - timedelta(days=1)), now)
    assert not _active(edge(ONE, TWO, valid_from=now + timedelta(seconds=1)), now)
    assert not _active(edge(ONE, TWO, valid_until=now), now)


def test_cyclic_graph_traversal_is_bounded_and_deterministic() -> None:
    adjacency = _adjacency(
        [edge(ONE, TWO), edge(TWO, THREE), edge(THREE, ONE)], "outgoing"
    )
    request = GraphQueryRequest(root_ids=[ONE], max_depth=5, max_nodes=10)
    visited, paths = _traverse(request, adjacency)
    assert visited == [ONE, TWO, THREE]
    assert paths == []


def test_path_query_returns_only_simple_paths() -> None:
    adjacency = _adjacency(
        [edge(ONE, TWO), edge(TWO, THREE), edge(THREE, ONE)], "outgoing"
    )
    request = GraphQueryRequest(
        root_ids=[ONE], mode="paths", target_id=THREE, direction="outgoing"
    )
    _, paths = _traverse(request, adjacency)
    assert paths == [[ONE, TWO, THREE]]


def test_access_filters_endpoints_and_provenance_before_edge_query() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    request = GraphQueryRequest(root_ids=[ONE])
    access = EvidenceAccessContext(
        actor="reader",
        projects=frozenset({"systematic-research"}),
        max_access_class="internal",
    )
    _authorized_edges(db, {ONE, TWO}, access, request)
    statement = db.scalars.call_args.args[0]
    compiled = repr(statement.compile().params)
    assert "protected" not in compiled
    assert str(ONE) in compiled and str(TWO) in compiled


def test_frontier_edge_query_is_bounded_to_requested_nodes() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    request = GraphQueryRequest(root_ids=[ONE], max_nodes=500)
    access = EvidenceAccessContext(
        actor="reader",
        projects=frozenset({"systematic-research"}),
        max_access_class="internal",
    )
    _frontier_edges(db, {ONE, TWO}, access, request)
    statement = db.scalars.call_args.args[0]
    parameters = statement.compile().params
    serialized = repr(parameters)
    assert str(ONE) in serialized and str(TWO) in serialized
    assert len(parameters) < 20


def test_graph_node_replay_path_targets_canonical_evidence_route() -> None:
    node = SimpleNamespace(
        object_id=ONE,
        object_type="scientific_object",
        project="systematic-research",
        access_class="internal",
        content_digest="a" * 64,
        label="Evidence",
    )

    response = _node_response(node)

    assert response["replay_path"] == (
        f"/v1/research/evidence/objects/{ONE}"
    )


def test_graph_cursor_is_bounded_to_exact_query_fingerprint() -> None:
    cursor = _encode_graph_cursor(40, "a" * 64)
    assert _decode_graph_cursor(cursor, "a" * 64) == 40
    with pytest.raises(HTTPException, match="does not match"):
        _decode_graph_cursor(cursor, "b" * 64)
    with pytest.raises(HTTPException, match="does not match"):
        _decode_graph_cursor("not-a-cursor", "a" * 64)


def test_graph_response_exposes_edge_access_and_explicit_truncation() -> None:
    projected_edge = SimpleNamespace(
        edge_id=THREE,
        subject_id=ONE,
        object_id=TWO,
        predicate="supports",
        valid_from=None,
        valid_until=None,
        provenance_object_id=THREE,
        access_class="restricted",
        record_digest="d" * 64,
    )
    edge_payload = _edge_response(projected_edge)
    assert edge_payload["access_class"] == "restricted"
    cursor = _encode_graph_cursor(1, "c" * 64)
    response = GraphQueryResponse.model_validate(
        {
            "projection_version": "knowledge-graph-v1.0.0",
            "corpus_digest": "a" * 64,
            "query_digest": "b" * 64,
            "nodes": [],
            "edges": [],
            "paths": [],
            "truncated": True,
            "page": {
                "cursor": None,
                "next_cursor": cursor,
                "page_size": 1,
                "offset": 0,
                "returned": 1,
                "traversed": 3,
            },
            "truncation": {
                "truncated": True,
                "reasons": ["page_size", "max_nodes"],
                "max_nodes": 3,
                "max_depth": 2,
            },
        }
    )
    assert response.page.next_cursor == cursor
    assert response.truncation.reasons == ["page_size", "max_nodes"]


def test_canonical_neighborhood_pages_are_deterministic_and_keep_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(
        projection_version="knowledge-graph-v1.0.0", corpus_digest="a" * 64
    )
    nodes = {
        item: SimpleNamespace(
            object_id=item,
            object_type="claim" if item != THREE else "scientific_object",
            project="systematic-research",
            access_class="internal",
            content_digest=str(item.int % 10) * 64,
            label=f"Node {item}",
        )
        for item in (ONE, TWO, THREE)
    }
    projected_edge = SimpleNamespace(
        edge_id=UUID("44444444-4444-4444-8444-444444444444"),
        subject_id=ONE,
        object_id=TWO,
        predicate="supports",
        valid_from=None,
        valid_until=None,
        provenance_object_id=THREE,
        access_class="internal",
        record_digest="d" * 64,
    )
    monkeypatch.setattr(
        "app.services.graph.graph_projection_status", lambda _: (state, False)
    )
    monkeypatch.setattr(
        "app.services.graph._authorized_node_subset",
        lambda _db, ids, _access, _project, **_kwargs: {
            item: nodes[item] for item in ids
        },
    )
    monkeypatch.setattr(
        "app.services.graph._frontier_edges",
        lambda *_args, **_kwargs: [projected_edge],
    )
    access = EvidenceAccessContext(
        actor="reader",
        projects=frozenset({"systematic-research"}),
        max_access_class="internal",
    )
    request = GraphQueryRequest(
        root_ids=[ONE],
        direction="outgoing",
        max_depth=1,
        max_nodes=10,
        page_size=1,
    )

    first = query_graph(MagicMock(), request, access)
    assert [node["id"] for node in first["nodes"]] == [ONE]
    assert first["page"]["next_cursor"]
    assert "page_size" in first["truncation"]["reasons"]

    second = query_graph(
        MagicMock(),
        request.model_copy(update={"cursor": first["page"]["next_cursor"]}),
        access,
    )
    assert {node["id"] for node in second["nodes"]} == {ONE, TWO, THREE}
    assert second["edges"][0]["provenance_object_id"] == THREE
    assert second["edges"][0]["access_class"] == "internal"
    assert second["page"]["next_cursor"] is None


def test_stale_projection_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    state = SimpleNamespace(corpus_digest="1" * 64, source_epoch=41)
    db = MagicMock()
    db.get.return_value = state
    monkeypatch.setattr("app.services.graph.corpus_epoch", lambda _: 42)
    assert graph_projection_status(db) == (state, True)


def test_current_projection_uses_constant_time_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(corpus_digest="1" * 64, source_epoch=42)
    db = MagicMock()
    db.get.return_value = state
    monkeypatch.setattr("app.services.graph.corpus_epoch", lambda _: 42)
    assert graph_projection_status(db) == (state, False)


def test_legacy_projection_adopts_epoch_only_after_digest_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(corpus_digest="1" * 64, source_epoch=0)
    db = MagicMock()
    db.get.return_value = state
    monkeypatch.setattr("app.services.graph.corpus_epoch", lambda _: 42)
    monkeypatch.setattr(
        "app.services.graph.graph_corpus_digest", lambda _: "1" * 64
    )

    assert graph_projection_status(db) == (state, False)
    assert state.source_epoch == 42
    db.commit.assert_called_once()


def test_legacy_projection_does_not_adopt_epoch_when_digest_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(corpus_digest="1" * 64, source_epoch=0)
    db = MagicMock()
    db.get.return_value = state
    monkeypatch.setattr("app.services.graph.corpus_epoch", lambda _: 42)
    monkeypatch.setattr(
        "app.services.graph.graph_corpus_digest", lambda _: "2" * 64
    )

    assert graph_projection_status(db) == (state, True)
    assert state.source_epoch == 0
    db.commit.assert_not_called()


def test_deterministic_calculators_have_stable_parity() -> None:
    assert calculate("mean", [1, 2, 3], {})["value"] == 2.0
    deviation = calculate("sample-standard-deviation", [1, 2, 3], {})
    assert deviation["value"] == 1.0
    drawdown = calculate("max-drawdown", [100, 120, 90, 110], {})
    assert drawdown["value"] == 0.25
    first = calculate("sharpe", [0.01, 0.02, -0.01], {"periods_per_year": 252})
    second = calculate("sharpe", [0.01, 0.02, -0.01], {"periods_per_year": 252})
    assert first == second
    assert digest_document(first) == digest_document(second)


def test_calculators_reject_undefined_sample_statistics() -> None:
    with pytest.raises(HTTPException, match="two values"):
        calculate("sample-standard-deviation", [1], {})


def test_tool_execution_persists_and_reuses_digest_bound_receipt() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    access = EvidenceAccessContext(
        actor="independent-evaluator",
        projects=frozenset({"systematic-research"}),
        max_access_class="internal",
    )
    request = CognitiveToolRequest(tool="mean", values=[1, 2, 3])
    receipt = execute_cognitive_tool(db, request, access)
    assert receipt.result["value"] == 2.0
    assert receipt.receipt_digest == digest_document(
        {
            "tool": "mean",
            "tool_version": "deterministic-scientific-tools-v1.0.0",
            "input_digest": receipt.input_digest,
            "output_digest": receipt.output_digest,
            "context_pack_digest": None,
            "actor": "independent-evaluator",
        }
    )
    db.add.assert_called_once_with(receipt)
    db.commit.assert_called_once_with()

    replay = MagicMock()
    replay.scalar.return_value = receipt
    assert execute_cognitive_tool(replay, request, access) is receipt
    replay.add.assert_not_called()
