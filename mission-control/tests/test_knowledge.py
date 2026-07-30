from __future__ import annotations

from pathlib import Path

import pytest

from hermes_mission_control.knowledge import (
    KnowledgePolicyError,
    KnowledgeStore,
)


@pytest.fixture
def store(tmp_path: Path) -> tuple[KnowledgeStore, Path]:
    root = tmp_path / "approved"
    root.mkdir()
    knowledge = KnowledgeStore(tmp_path / "data" / "knowledge.sqlite3", (root,))
    knowledge.initialize()
    return knowledge, root


def test_ingest_search_citations_and_graph(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "strategy.md"
    source.write_text(
        "# Hermes Strategy\n\n"
        "Hermes uses bounded workers for infrastructure evidence.\n\n"
        "The [[Control Plane]] coordinates the #research program.\n",
        encoding="utf-8",
    )
    result = knowledge.ingest(str(source))
    matches = knowledge.search("infrastructure evidence")
    graph = knowledge.graph()
    assert result.chunks == 3
    assert result.unchanged is False
    assert matches[0].title == "Hermes Strategy"
    assert matches[0].citation.endswith("strategy.md#L3-L3")
    assert matches[0].digest == result.digest
    assert {node.name for node in graph.nodes} >= {
        "Hermes Strategy",
        "Control Plane",
        "research",
    }
    assert graph.edges


def test_unchanged_document_is_deduplicated(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "note.txt"
    source.write_text("Private decision evidence.", encoding="utf-8")
    first = knowledge.ingest(str(source))
    second = knowledge.ingest(str(source))
    assert first.source_id == second.source_id
    assert second.unchanged is True
    assert knowledge.stats()["sources"] == 1


def test_changed_document_reindexes_without_duplicate_search_rows(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "note.md"
    source.write_text("First uniquephrase.", encoding="utf-8")
    knowledge.ingest(str(source))
    source.write_text("Second replacementphrase.", encoding="utf-8")
    knowledge.ingest(str(source))
    assert knowledge.search("uniquephrase") == []
    assert len(knowledge.search("replacementphrase")) == 1


def test_outside_root_is_rejected(
    store: tuple[KnowledgeStore, Path], tmp_path: Path
) -> None:
    knowledge, _ = store
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(KnowledgePolicyError, match="outside approved roots"):
        knowledge.ingest(str(outside))


def test_symlink_escape_is_rejected(
    store: tuple[KnowledgeStore, Path], tmp_path: Path
) -> None:
    knowledge, root = store
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    link = root / "link.md"
    link.symlink_to(outside)
    with pytest.raises(KnowledgePolicyError, match="outside approved roots"):
        knowledge.ingest(str(link))


def test_relative_path_and_unsupported_type_rejected(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    binary = root / "data.pdf"
    binary.write_bytes(b"%PDF")
    with pytest.raises(KnowledgePolicyError, match="absolute"):
        knowledge.ingest("notes.md")
    with pytest.raises(KnowledgePolicyError, match="Markdown"):
        knowledge.ingest(str(binary))


def test_search_syntax_is_treated_as_terms(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "query.md"
    source.write_text("Alpha beta gamma.", encoding="utf-8")
    knowledge.ingest(str(source))
    assert knowledge.search('alpha" OR *') == []
    assert knowledge.search("alpha beta")

