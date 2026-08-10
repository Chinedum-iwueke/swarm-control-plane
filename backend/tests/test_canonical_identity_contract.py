from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.contracts.canonical_identity import (
    IdentityCompatibilityError,
    assert_immutable_identity,
    normalize_identity,
)

FIXTURES = Path(__file__).parent / "fixtures" / "canonical_identity"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_canonical_record_round_trips() -> None:
    document = load("canonical-v1.json")
    assert normalize_identity(document) == document


def test_legacy_hermes_record_receives_immutable_alias() -> None:
    legacy = load("legacy-hermes-v0.json")
    value = normalize_identity(
        legacy,
        object_type="research.hypothesis",
        namespace="hermes",
    )
    assert value["object_id"] == legacy["id"]
    assert value["content_digest"] == legacy["record_digest"]
    assert value["aliases"][0]["value"] == legacy["id"]


def test_digest_mutation_is_rejected() -> None:
    previous = load("canonical-v1.json")
    current = {**previous, "content_digest": "c" * 64}
    with pytest.raises(IdentityCompatibilityError, match="digest mutation"):
        assert_immutable_identity(previous, current)


def test_unknown_major_version_is_rejected() -> None:
    document = {**load("canonical-v1.json"), "schema_version": "canonical-identity-v2.0.0"}
    with pytest.raises(IdentityCompatibilityError, match="unsupported"):
        normalize_identity(document)


def test_non_uuid_producer_id_requires_canonical_uuid() -> None:
    legacy = {"run_id": "run-btc-001", "artifact_digest": "d" * 64}
    value = normalize_identity(
        legacy,
        object_type="research.trial",
        namespace="bulletproof",
        id_field="run_id",
        digest_field="artifact_digest",
        canonical_object_id="33333333-3333-4333-8333-333333333333",
    )
    assert value["object_id"] == "33333333-3333-4333-8333-333333333333"
    assert value["aliases"][0]["value"] == "run-btc-001"
