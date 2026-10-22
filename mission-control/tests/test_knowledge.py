from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hermes_mission_control.knowledge import (
    KnowledgePolicyError,
    KnowledgeStore,
    LocalGraphQueryError,
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


def test_private_source_content_uses_stable_opaque_id_and_versions(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "versioned.md"
    source.write_text("# Versioned\n\nfirst\nsecond\nthird", encoding="utf-8")
    knowledge.ingest(str(source))
    first_catalog = knowledge.catalog()
    opaque_id = str(first_catalog[0]["opaque_id"])
    assert first_catalog[0]["id"] == opaque_id
    assert "path" not in first_catalog[0]

    first = knowledge.source_content(opaque_id, start=2, limit=2)
    assert first is not None
    assert first["source_id"] == opaque_id
    assert first["version"] == "1"
    assert first["range"]["next_start"] == 4
    assert "path" not in first
    assert first["citation"] == f"private:{opaque_id}@v1#L2-L3"
    assert first["outline"][0]["label"] == "Versioned"
    assert first["lineage"]["quality"] == "native_text"

    source.write_text("# Versioned\n\nupdated", encoding="utf-8")
    knowledge.ingest(str(source))
    second_catalog = knowledge.catalog()
    second = knowledge.source_content(opaque_id)
    assert second_catalog[0]["opaque_id"] == opaque_id
    assert second is not None
    assert second["version"] == "2"
    assert second["source_digest"] != first["source_digest"]


def test_private_source_content_is_bounded_and_unknown_ids_are_absent(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "large.txt"
    source.write_text("x" * 70_000, encoding="utf-8")
    knowledge.ingest(str(source))
    opaque_id = str(knowledge.catalog()[0]["opaque_id"])
    result = knowledge.source_content(opaque_id)

    assert result is not None
    assert len(result["content"].encode("utf-8")) <= 64 * 1024
    assert result["range"]["truncated_by_size"] is True
    assert result["original_assets"][0]["availability"] == "unavailable"
    assert knowledge.source_content("not-a-real-private-source-id") is None


def test_existing_private_index_is_migrated_to_opaque_versioned_sources(
    tmp_path: Path,
) -> None:
    database = tmp_path / "knowledge.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute(
            """
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, digest TEXT NOT NULL,
                modified_at TEXT NOT NULL, indexed_at TEXT NOT NULL,
                confidentiality TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO sources
                (path, title, digest, modified_at, indexed_at, confidentiality)
            VALUES ('/private/legacy.md', 'Legacy', ?, 'now', 'now', 'private')
            """,
            ("a" * 64,),
        )

    knowledge = KnowledgeStore(database, (tmp_path,))
    knowledge.initialize()
    item = knowledge.catalog()[0]

    assert item["id"] == item["opaque_id"]
    assert item["version"] == 1
    assert "path" not in item


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


def test_private_graph_has_stable_ids_provenance_and_cursor_pages(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    first = root / "first.md"
    first.write_text(
        "# First source\n\n[[Momentum]] and [[Liquidity]] are #signals.",
        encoding="utf-8",
    )
    second = root / "second.md"
    second.write_text("# Second source\n\n[[Volatility]] is observed.", encoding="utf-8")
    knowledge.ingest(str(first))
    knowledge.ingest(str(second))

    page_one = knowledge.graph_overview(limit=2)
    assert page_one["scope"] == "private"
    assert page_one["page"]["next_cursor"]
    assert page_one["truncation"]["reasons"] == ["page_size"]
    assert all(node["local_only"] for node in page_one["nodes"])

    page_two = knowledge.graph_overview(
        limit=2, cursor=str(page_one["page"]["next_cursor"])
    )
    assert {node["id"] for node in page_one["nodes"]}.isdisjoint(
        {node["id"] for node in page_two["nodes"]}
    )
    replay = knowledge.graph_overview(limit=2)
    assert [node["id"] for node in replay["nodes"]] == [
        node["id"] for node in page_one["nodes"]
    ]
    assert replay["query_digest"] == page_one["query_digest"]

    complete = knowledge.graph_overview(limit=100)
    source = next(
        node for node in complete["nodes"]
        if node["object_type"] == "private_source"
    )
    neighborhood = knowledge.query_graph(
        {
            "scope": "private",
            "root_ids": [source["id"]],
            "mode": "neighborhood",
            "predicates": ["mentions"],
            "direction": "outgoing",
            "max_depth": 1,
            "max_nodes": 10,
            "page_size": 10,
            "object_types": [],
        }
    )
    assert neighborhood["edges"]
    edge = neighborhood["edges"][0]
    assert edge["id"].startswith("private-edge:")
    assert edge["provenance"]["local_only"] is True
    assert edge["provenance"]["citation"].startswith("private:")
    assert edge["provenance_object_id"] == source["id"]


def test_private_graph_filters_paths_bounds_and_rejects_wrong_cursor(
    store: tuple[KnowledgeStore, Path],
) -> None:
    knowledge, root = store
    source = root / "network.md"
    source.write_text(
        "# Network\n\n[[Alpha]] [[Beta]] [[Gamma]] [[Delta]] [[Epsilon]]",
        encoding="utf-8",
    )
    other = root / "isolated.md"
    other.write_text("# Isolated\n\nNo linked concepts.", encoding="utf-8")
    knowledge.ingest(str(source))
    knowledge.ingest(str(other))
    overview = knowledge.graph_overview(limit=100)
    source_node = next(
        node for node in overview["nodes"] if node["label"] == "Network"
    )
    isolated_node = next(
        node for node in overview["nodes"] if node["label"] == "Isolated"
    )
    bounded_query = {
        "scope": "private",
        "root_ids": [source_node["id"]],
        "mode": "neighborhood",
        "predicates": ["mentions"],
        "direction": "outgoing",
        "max_depth": 2,
        "max_nodes": 3,
        "page_size": 1,
        "object_types": [],
    }
    first = knowledge.query_graph(bounded_query)
    assert first["page"]["next_cursor"]
    assert {"page_size", "max_nodes"} <= set(first["truncation"]["reasons"])
    second = knowledge.query_graph(
        {**bounded_query, "cursor": first["page"]["next_cursor"]}
    )
    assert second["page"]["offset"] == 1

    with pytest.raises(LocalGraphQueryError, match="does not match"):
        knowledge.query_graph(
            {
                **bounded_query,
                "max_depth": 1,
                "cursor": first["page"]["next_cursor"],
            }
        )

    no_path = knowledge.query_graph(
        {
            **bounded_query,
            "mode": "paths",
            "target_id": isolated_node["id"],
            "max_nodes": 20,
            "page_size": 20,
        }
    )
    assert no_path["paths"] == []
    assert "page_size" not in no_path["truncation"]["reasons"]

    source_only = knowledge.query_graph(
        {
            **bounded_query,
            "object_types": ["private_source"],
            "max_nodes": 20,
            "page_size": 20,
        }
    )
    assert [node["id"] for node in source_only["nodes"]] == [source_node["id"]]
    assert source_only["edges"] == []
