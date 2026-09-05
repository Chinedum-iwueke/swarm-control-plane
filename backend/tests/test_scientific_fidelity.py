import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    ScientificAdjudicationCreate,
    ScientificBenchmarkCreate,
    ScientificCorrectionCreate,
    ScientificRepresentationCreate,
)
from app.scientific_fidelity_pilot import _region, _table_grid
from app.services.scientific_fidelity import (
    ScientificFidelityConflict,
    adjudicate_representation,
    create_benchmark,
    evaluate_benchmark,
    expression_tree,
    normalize,
    normalize_layout,
    propose_correction,
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


def test_region_alignment_ignores_layout_but_not_symbol_changes():
    target = "Δpₜ = rₜ / σₜ"
    assert _region(f"heading\n{target}\nfooter", target) == target
    assert _region("heading\nΔpₜ = rₜ / vₜ\nfooter", target) == "Δpₜ = rₜ / vₜ"


def test_table_grid_normalizes_pipe_and_spacing_cells():
    assert _table_grid("a | b | c") == [["a", "b", "c"]]
    assert _table_grid("a  b  c") == [["a", "b", "c"]]


def test_layout_normalization_repairs_ligatures_and_line_wrap_only():
    assert (
        normalize_layout("we ﬁt a two- \u0002dimensional model")
        == "we fit a twodimensional model"
    )
    assert normalize_layout("Δpₜ = σₜ") == "Δpₜ = σₜ"


@pytest.mark.parametrize(
    ("expression", "kind"),
    [
        ("{x,y,z}", "set"),
        ("[x,y,z]", "vector"),
        ("(x,y)", "tuple"),
        ("2x", "implicit_product"),
    ],
)
def test_structured_mathematical_forms(expression, kind):
    tree, complete = expression_tree(semantic_tokens(expression))
    assert complete is True
    assert tree["kind"] == kind


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
            "figure_reference_replay": 0.99,
        },
        metrics={
            "token_precision": 1.0,
            "token_recall": 1.0,
            "cell_accuracy": 1.0,
            "expression_replay": 1.0,
            "figure_reference_replay": 1.0,
        },
        created_by="ri014-pilot",
    )
    assert publish_manifest(db, request).status == "not_qualified"


def test_openapi_exposes_fidelity_review_and_manifest_contracts():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/v1/research/scientific-fidelity/representations" in paths
    assert "/v1/research/scientific-fidelity/manifests" in paths
    assert "/v1/research/scientific-fidelity/adjudications" in paths
    assert "/v1/research/scientific-fidelity/review-queue" in paths
    assert (
        "/v1/research/scientific-fidelity/review-context/{representation_id}" in paths
    )
    assert "/v1/research/scientific-fidelity/benchmarks" in paths
    assert "/v1/research/scientific-fidelity/corrections" in paths


def test_producer_cannot_self_adjudicate():
    representation = SimpleNamespace(
        created_by="parser-agent", source_region_digest="a" * 64
    )
    db = MagicMock()
    db.get.return_value = representation
    request = ScientificAdjudicationCreate(
        representation_id=uuid.uuid4(),
        reviewer_id="parser-agent",
        reviewer_role="independent_evaluator",
        decision="equivalent",
        rationale="Exact source comparison was completed.",
        corpus_digest="b" * 64,
    )
    with pytest.raises(ScientificFidelityConflict, match="cannot adjudicate"):
        adjudicate_representation(db, request)


def test_adjudication_creates_hash_chained_event():
    representation = SimpleNamespace(
        created_by="parser-agent", source_region_digest="a" * 64
    )
    db = MagicMock()
    db.get.return_value = representation
    db.scalar.return_value = None
    request = ScientificAdjudicationCreate(
        representation_id=uuid.uuid4(),
        reviewer_id="reviewer-one",
        reviewer_role="independent_evaluator",
        decision="material_mismatch",
        rationale="The denominator symbol differs from the source.",
        corpus_digest="b" * 64,
    )
    record = adjudicate_representation(db, request)
    assert record.independent_of_producer is True
    event = db.add.call_args_list[1].args[0]
    assert event.previous_digest == "0" * 64
    assert len(event.event_digest) == 64


def test_benchmark_sampling_is_deterministic_and_stratified():
    records = [
        SimpleNamespace(id=uuid.uuid4(), scientific_type=kind)
        for kind in ("equation", "equation", "table", "figure")
    ]
    db = MagicMock()
    db.scalars.return_value.all.return_value = records
    db.scalar.return_value = None
    request = ScientificBenchmarkCreate(
        benchmark_version="held-out-v1",
        representation_version="scientific-fidelity-v2.0.0",
        corpus_digest="c" * 64,
        sample_seed="fixed-seed",
        per_type={"equation": 1, "table": 1, "figure": 1},
        created_by="benchmark-operator",
    )
    first = create_benchmark(db, request)
    second = create_benchmark(db, request)
    assert first.sampled_representation_ids == second.sampled_representation_ids
    assert len(first.sampled_representation_ids) == 3


def test_benchmark_uses_adjudications_as_ground_truth():
    benchmark_id = uuid.uuid4()
    rep_a = SimpleNamespace(
        id=uuid.uuid4(), status="accepted", scientific_type="equation"
    )
    rep_b = SimpleNamespace(
        id=uuid.uuid4(), status="review_required", scientific_type="table"
    )
    benchmark = SimpleNamespace(
        sampled_representation_ids=[str(rep_a.id), str(rep_b.id)],
        evaluation_digest=None,
        record_digest="c" * 64,
        sample_spec={
            "thresholds": {
                "class_precision": 0.9,
                "class_recall": 0.9,
                "coverage": 1.0,
                "escape_rate": 0.0,
            }
        },
    )
    labels = [
        SimpleNamespace(
            representation_id=rep_a.id, decision="equivalent", record_digest="a" * 64
        ),
        SimpleNamespace(
            representation_id=rep_b.id,
            decision="material_mismatch",
            record_digest="b" * 64,
        ),
    ]
    db = MagicMock()
    db.get.return_value = benchmark
    db.scalars.side_effect = [
        MagicMock(all=lambda: [rep_a, rep_b]),
        MagicMock(all=lambda: labels),
    ]
    result = evaluate_benchmark(db, benchmark_id)
    assert result.status == "qualified"
    assert result.metrics["class_precision"] == 1.0
    assert result.metrics["abstention_accuracy"] == 1.0


def test_correction_requires_new_version_and_separate_actor():
    adjudication = SimpleNamespace(
        id=uuid.uuid4(),
        representation_id=uuid.uuid4(),
        reviewer_id="reviewer",
        decision="material_mismatch",
    )
    representation = SimpleNamespace(
        representation_version="scientific-fidelity-v2.0.0"
    )
    db = MagicMock()
    db.get.side_effect = [adjudication, representation]
    request = ScientificCorrectionCreate(
        adjudication_id=adjudication.id,
        proposed_version="scientific-fidelity-v2.0.0",
        proposed_payload={"content": "x"},
        proposer_id="repair-agent",
    )
    with pytest.raises(ScientificFidelityConflict, match="new representation version"):
        propose_correction(db, request)
