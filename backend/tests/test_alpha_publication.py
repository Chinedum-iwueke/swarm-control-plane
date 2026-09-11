from types import SimpleNamespace

import pytest
from app.services.alpha_publication import (
    _has_founder_execution_authority,
    _require_current_projections,
)
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
    decision = SimpleNamespace(effective_roles=["research"])
    db = SimpleNamespace(scalar=lambda _: decision)

    assert _has_founder_execution_authority(db, approval) is False


@pytest.mark.parametrize(
    "graph,retrieval,corpus",
    [
        (None, SimpleNamespace(source_epoch=7, corpus_digest="a" * 64), SimpleNamespace(epoch=7, corpus_digest="a" * 64)),
        (SimpleNamespace(source_epoch=6), SimpleNamespace(source_epoch=7, corpus_digest="a" * 64), SimpleNamespace(epoch=7, corpus_digest="a" * 64)),
        (SimpleNamespace(source_epoch=7), SimpleNamespace(source_epoch=6, corpus_digest="a" * 64), SimpleNamespace(epoch=7, corpus_digest="a" * 64)),
        (SimpleNamespace(source_epoch=7), SimpleNamespace(source_epoch=7, corpus_digest="b" * 64), SimpleNamespace(epoch=7, corpus_digest="a" * 64)),
    ],
)
def test_alpha_publication_fails_closed_for_missing_or_stale_projection(
    graph, retrieval, corpus
) -> None:
    with pytest.raises(HTTPException, match="stale"):
        _require_current_projections(graph, retrieval, corpus)
