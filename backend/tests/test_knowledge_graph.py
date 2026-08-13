from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.graph import (
    CanonicalEdgeCreate,
    CognitiveToolRequest,
    GraphQueryRequest,
)
from app.services.evidence import EvidenceAccessContext
from app.services.graph import (
    _active,
    _adjacency,
    _authorized_edges,
    _traverse,
    _validate_edge_types,
    calculate,
    digest_document,
    execute_cognitive_tool,
    graph_projection_status,
)

ONE = UUID("11111111-1111-4111-8111-111111111111")
TWO = UUID("22222222-2222-4222-8222-222222222222")
THREE = UUID("33333333-3333-4333-8333-333333333333")


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


def test_stale_projection_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    state = SimpleNamespace(corpus_digest="1" * 64)
    db = MagicMock()
    db.get.return_value = state
    monkeypatch.setattr("app.services.graph.graph_corpus_digest", lambda _: "2" * 64)
    assert graph_projection_status(db) == (state, True)


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
