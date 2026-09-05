import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    ScientificRepresentationCreate,
)
from app.services.scientific_fidelity import (
    ScientificFidelityConflict,
    expression_tree,
    normalize,
    publish_manifest,
    register_representation,
    semantic_tokens,
)


def payload(**overrides):
    values = {
        "source_object_id": uuid.uuid4(),
        "scientific_type": "equation",
        "source_region_digest": hashlib.sha256(b"region").hexdigest(),
        "parser_outputs": [
            {
                "parser": "pypdf",
                "method": "native",
                "content": "Δpₜ = rₜ / σₜ",
                "confidence": 0.99,
            },
            {
                "parser": "mathml",
                "method": "structural",
                "content": "Δpₜ = rₜ / σₜ",
                "confidence": 0.98,
            },
        ],
        "symbols": [
            {"symbol": "Δpₜ", "definition": "price displacement", "scope": "equation:1"}
        ],
        "units": [{"symbol": "Δpₜ", "unit": "return", "dimension": "dimensionless"}],
        "created_by": "ri014-pilot",
    }
    values.update(overrides)
    return ScientificRepresentationCreate.model_validate(values)


def fake_db(value):
    db = MagicMock()
    db.get.return_value = value
    db.scalar.return_value = None
    return db


def test_unicode_and_semantic_tokens_preserve_mathematical_symbols():
    assert normalize("  Δpₜ   =  rₜ / σₜ ") == "Δpₜ = rₜ / σₜ"
    values = [item["value"] for item in semantic_tokens("∫ π(x) dx ≥ δ")]
    assert "∫" in values and "π" in values and "δ" in values and "≥" in values


def test_equation_tree_preserves_fraction_precedence():
    tree, complete = expression_tree(semantic_tokens("Δpₜ = rₜ / σₜ"))
    assert complete is True
    assert tree["operator"] == "="
    assert tree["right"]["operator"] == "/"


def test_two_independent_parsers_accept_equation():
    source = SimpleNamespace(
        object_type="scientific_object", payload={"scientific_type": "equation"}
    )
    record = register_representation(fake_db(source), payload())
    assert record.status == "accepted"
    assert record.semantic_payload["symbols"][0]["scope"] == "equation:1"


def test_material_parser_disagreement_requires_review():
    source = SimpleNamespace(
        object_type="scientific_object", payload={"scientific_type": "equation"}
    )
    changed = payload(
        parser_outputs=[
            {
                "parser": "pypdf",
                "method": "native",
                "content": "x = 1 / y",
                "confidence": 0.99,
            },
            {
                "parser": "ocr",
                "method": "ocr",
                "content": "x = l / y",
                "confidence": 0.95,
            },
        ]
    )
    record = register_representation(fake_db(source), changed)
    assert record.status == "review_required"
    assert any(item["kind"] == "material_disagreement" for item in record.uncertainties)


def test_ocr_only_cannot_be_accepted():
    source = SimpleNamespace(
        object_type="scientific_object", payload={"scientific_type": "equation"}
    )
    changed = payload(
        parser_outputs=[
            {
                "parser": "ocr-a",
                "method": "ocr",
                "content": "x = y",
                "confidence": 0.99,
            },
            {
                "parser": "ocr-b",
                "method": "ocr",
                "content": "x = y",
                "confidence": 0.99,
            },
        ]
    )
    assert register_representation(fake_db(source), changed).status == "review_required"


def test_dimensional_conflict_requires_review():
    source = SimpleNamespace(
        object_type="scientific_object", payload={"scientific_type": "equation"}
    )
    changed = payload(
        units=[
            {"symbol": "x", "unit": "second", "dimension": "time"},
            {"symbol": "x", "unit": "metre", "dimension": "length"},
        ]
    )
    record = register_representation(fake_db(source), changed)
    assert record.status == "review_required"
    assert any(item["kind"] == "dimensional_conflict" for item in record.uncertainties)


def test_source_type_must_match():
    source = SimpleNamespace(
        object_type="scientific_object", payload={"scientific_type": "table"}
    )
    with pytest.raises(ScientificFidelityConflict, match="types do not match"):
        register_representation(fake_db(source), payload())


def test_table_requires_cell_grid():
    with pytest.raises(ValueError, match="table_grid"):
        payload(scientific_type="table")


def test_manifest_does_not_qualify_with_review_work():
    accepted = SimpleNamespace(status="accepted", record_digest="a" * 64)
    review = SimpleNamespace(status="review_required", record_digest="b" * 64)
    db = MagicMock()
    db.scalars.return_value.all.return_value = [accepted, review]
    db.scalar.return_value = None
    request = FidelityManifestCreate(
        corpus_digest="c" * 64,
        thresholds={
            "token_precision": 0.99,
            "token_recall": 0.99,
            "cell_accuracy": 0.99,
            "expression_replay": 1.0,
        },
        metrics={
            "token_precision": 1.0,
            "token_recall": 1.0,
            "cell_accuracy": 1.0,
            "expression_replay": 1.0,
        },
        created_by="ri014-pilot",
    )
    assert publish_manifest(db, request).status == "not_qualified"


def test_openapi_exposes_fidelity_review_and_manifest_contracts():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/v1/research/scientific-fidelity/representations" in paths
    assert "/v1/research/scientific-fidelity/manifests" in paths
