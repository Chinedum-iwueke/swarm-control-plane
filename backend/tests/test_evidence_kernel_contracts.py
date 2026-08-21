from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from app.models.evidence import CanonicalEvidenceObject, CanonicalIdentityAlias
from app.schemas.evidence import EvidenceObjectCreate
from app.services.evidence import (
    EvidenceAccessContext,
    canonical_payload_digest,
    get_evidence_object,
    register_evidence_object,
)
from fastapi import HTTPException
from pydantic import ValidationError

NOW = datetime(2026, 8, 10, tzinfo=UTC)
DIGEST = "a" * 64
OBJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
SOURCE_ID = UUID("22222222-2222-4222-8222-222222222222")
EDITION_ID = UUID("33333333-3333-4333-8333-333333333333")
ARTIFACT_ID = UUID("44444444-4444-4444-8444-444444444444")
CLAIM_ID = UUID("55555555-5555-4555-8555-555555555555")
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "evidence_kernel"

ACCESS = EvidenceAccessContext(
    actor="knowledge-steward",
    projects=frozenset({"systematic-research"}),
    max_access_class="protected",
    may_write=True,
)


def payloads() -> dict[str, tuple[str, dict]]:
    return {
        "source": (
            "primary",
            {
                "kind": "source",
                "title": "Synthetic source",
                "origin": "fixture://source",
                "rights": "fixture-only",
                "acquired_at": NOW,
            },
        ),
        "edition": (
            "primary",
            {
                "kind": "edition",
                "source_object_id": SOURCE_ID,
                "edition_label": "first",
                "published_at": NOW,
            },
        ),
        "artifact": (
            "primary",
            {
                "kind": "artifact",
                "edition_object_id": EDITION_ID,
                "media_type": "application/pdf",
                "storage_uri": "object://fixture/paper.pdf",
                "byte_size": 100,
                "artifact_digest": DIGEST,
            },
        ),
        "scientific_object": (
            "derived",
            {
                "kind": "scientific_object",
                "artifact_object_id": ARTIFACT_ID,
                "scientific_type": "equation",
                "parent_object_id": None,
                "coordinates": {"page": 2, "x": 0.1},
                "extraction_method": "fixture-parser-v1",
                "extraction_confidence": 0.99,
            },
        ),
        "claim": (
            "derived",
            {
                "kind": "claim",
                "proposition": "Momentum is positive in the fixture.",
                "evidence_object_ids": [ARTIFACT_ID],
                "qualifiers": ["synthetic"],
                "status": "proposed",
            },
        ),
        "method": (
            "derived",
            {
                "kind": "method",
                "name": "Purged validation",
                "procedure": "Split observations without temporal overlap.",
                "evidence_object_ids": [ARTIFACT_ID],
                "assumption_object_ids": [],
            },
        ),
        "assumption": (
            "derived",
            {
                "kind": "assumption",
                "statement": "Costs are stationary within the fixture.",
                "scope": "Synthetic observations only.",
                "evidence_object_ids": [],
            },
        ),
        "dataset": (
            "primary",
            {
                "kind": "dataset",
                "source_object_ids": [SOURCE_ID],
                "schema_digest": "b" * 64,
                "partition_digests": ["c" * 64],
                "availability_policy": "Point-in-time fixture.",
                "correction_object_ids": [],
            },
        ),
        "run": (
            "operational",
            {
                "kind": "run",
                "dataset_object_ids": [SOURCE_ID],
                "specification_digest": "b" * 64,
                "code_digest": "c" * 64,
                "environment_digest": "d" * 64,
                "attempt": 1,
            },
        ),
        "review": (
            "institutional",
            {
                "kind": "review",
                "subject_object_id": CLAIM_ID,
                "subject_digest": "b" * 64,
                "reviewer_authority": "statistical-reviewer",
                "verdict": "rejected",
                "rationale": "The evidence is insufficient.",
            },
        ),
        "decision": (
            "institutional",
            {
                "kind": "decision",
                "evidence_object_ids": [CLAIM_ID],
                "decided_by_authority": "research-governance",
                "decision": "retain-negative-result",
                "rationale": "Retain it as negative evidence.",
                "valid_from": NOW,
                "valid_until": None,
            },
        ),
        "belief": (
            "institutional",
            {
                "kind": "belief",
                "claim_object_id": CLAIM_ID,
                "supporting_evidence_ids": [],
                "opposing_evidence_ids": [ARTIFACT_ID],
                "assessment": "The claim is presently weak.",
                "confidence": 0.8,
                "owner": "knowledge-steward",
                "reviewers": ["statistical-reviewer"],
                "valid_from": NOW,
                "valid_until": None,
            },
        ),
        "episode": (
            "operational",
            {
                "kind": "episode",
                "task_id": None,
                "input_object_ids": [CLAIM_ID],
                "output_object_ids": [],
                "tools": ["bulletproof"],
                "failures": ["acceptance gate failed"],
                "decision_object_ids": [],
                "lessons": ["retain negative evidence"],
                "protected_references": ["vault://fixture/redacted"],
            },
        ),
    }


def make_create(object_type: str, authority: str, body: dict) -> EvidenceObjectCreate:
    digest = DIGEST if object_type == "artifact" else canonical_payload_digest(
        _json_payload(body)
    )
    native_id = f"fixture-{object_type}"
    return EvidenceObjectCreate.model_validate(
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": OBJECT_ID,
            "object_type": object_type,
            "content_version": "1",
            "content_digest": digest,
            "producer": {
                "system": "hermes",
                "native_type": object_type,
                "native_id": native_id,
                "schema_version": "fixture-v1",
            },
            "aliases": [
                {"namespace": "hermes", "object_type": object_type, "value": native_id}
            ],
            "supersedes_object_id": None,
            "project": "systematic-research",
            "access_class": "internal",
            "authority_class": authority,
            "payload": body,
            "created_by": "knowledge-steward",
        }
    )


def _json_payload(body: dict) -> dict:
    from pydantic_core import to_jsonable_python

    return to_jsonable_python(body)


@pytest.mark.parametrize("object_type", list(payloads()))
def test_all_required_object_contracts_validate(object_type: str) -> None:
    authority, body = payloads()[object_type]
    value = make_create(object_type, authority, body)
    assert value.payload.kind == object_type


def test_unknown_fields_and_authority_conflation_are_rejected() -> None:
    _, body = payloads()["claim"]
    with pytest.raises(ValidationError, match="authority_class"):
        make_create("claim", "institutional", body)
    body = {**body, "model_says": "approve"}
    with pytest.raises(ValidationError, match="Extra inputs"):
        make_create("claim", "derived", body)


def test_unknown_identity_and_object_major_versions_are_rejected() -> None:
    authority, body = payloads()["source"]
    valid = make_create("source", authority, body).model_dump(mode="json")
    with pytest.raises(ValidationError, match="schema_version"):
        EvidenceObjectCreate.model_validate(
            {**valid, "schema_version": "canonical-identity-v2.0.0"}
        )
    with pytest.raises(ValidationError, match="object_schema_version"):
        EvidenceObjectCreate.model_validate(
            {**valid, "object_schema_version": "canonical-evidence-v2.0.0"}
        )


def test_digest_mismatch_fails_before_database_write() -> None:
    authority, body = payloads()["source"]
    value = make_create("source", authority, body).model_copy(
        update={"content_digest": "0" * 64}
    )
    db = MagicMock()
    with pytest.raises(HTTPException, match="digest mismatch"):
        register_evidence_object(db, value, ACCESS)
    db.add.assert_not_called()


def test_registration_is_append_only_and_audited() -> None:
    authority, body = payloads()["source"]
    value = make_create("source", authority, body)
    db = MagicMock()
    db.get.return_value = None
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = []
    db.refresh.side_effect = lambda record: setattr(record, "created_at", NOW)

    record = register_evidence_object(db, value, ACCESS)

    assert record.id == OBJECT_ID
    assert db.add.call_count == 4
    db.commit.assert_called_once_with()


def test_exact_registration_is_idempotent_but_mutation_conflicts() -> None:
    authority, body = payloads()["source"]
    value = make_create("source", authority, body)
    record = CanonicalEvidenceObject(
        id=value.object_id,
        schema_version=value.schema_version,
        object_schema_version=value.object_schema_version,
        object_type=value.object_type,
        content_version=value.content_version,
        content_digest=value.content_digest,
        producer=value.producer.model_dump(mode="json"),
        supersedes_object_id=None,
        project=value.project,
        access_class=value.access_class,
        authority_class=value.authority_class,
        payload=value.payload.model_dump(mode="json"),
        created_by=value.created_by,
    )
    record.created_at = NOW
    record.aliases = [
        CanonicalIdentityAlias(
            namespace="hermes",
            native_object_type="source",
            alias_value="fixture-source",
            canonical_object_id=value.object_id,
            canonical_object_type="source",
            producer_schema_version="fixture-v1",
        )
    ]
    db = MagicMock()
    db.get.return_value = record
    assert register_evidence_object(db, value, ACCESS) is record
    db.add.assert_not_called()

    changed_body = {**body, "title": "Mutated source"}
    changed = make_create("source", authority, changed_body)
    with pytest.raises(HTTPException, match="identity is immutable"):
        register_evidence_object(db, changed, ACCESS)


def test_missing_lineage_reference_is_rejected() -> None:
    authority, body = payloads()["claim"]
    value = make_create("claim", authority, body)
    db = MagicMock()
    db.get.return_value = None
    db.scalars.return_value.all.return_value = []
    with pytest.raises(HTTPException, match="lineage reference is missing"):
        register_evidence_object(db, value, ACCESS)
    db.commit.assert_not_called()


def test_read_access_denies_protected_payload_without_clearance() -> None:
    record = SimpleNamespace(
        id=OBJECT_ID,
        project="systematic-research",
        access_class="protected",
    )
    db = MagicMock()
    db.get.return_value = record
    reader = EvidenceAccessContext(
        actor="research-runner",
        projects=frozenset({"systematic-research"}),
        max_access_class="restricted",
    )
    with pytest.raises(HTTPException, match="access class"):
        get_evidence_object(db, OBJECT_ID, reader)
    db.add.assert_not_called()


def test_cross_project_write_is_denied() -> None:
    authority, body = payloads()["source"]
    value = make_create("source", authority, body).model_copy(
        update={"project": "other-project"}
    )
    with pytest.raises(HTTPException, match="project access"):
        register_evidence_object(MagicMock(), value, ACCESS)


def test_migration_has_upgrade_and_safe_prewrite_downgrade() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/c5e8a1d42f60_add_canonical_evidence_kernel.py"
    ).read_text(encoding="utf-8")
    for table in (
        "canonical_evidence_objects",
        "canonical_identity_aliases",
        "canonical_evidence_edges",
        "canonical_evidence_audit_events",
    ):
        assert table in migration
    assert "def downgrade()" in migration


def test_openapi_exposes_authenticated_immutable_object_routes() -> None:
    from app.main import app

    snapshot = json.loads(
        (FIXTURE_ROOT / "openapi-surface-v1.json").read_text(encoding="utf-8")
    )
    document = app.openapi()
    paths = document["paths"]
    actual_routes = {
        path: sorted(paths[path])
        for path in snapshot["routes"]
    }
    assert actual_routes == snapshot["routes"]
    assert "delete" not in paths["/v1/research/evidence/objects/{object_id}"]
    for path, methods in snapshot["routes"].items():
        for method in methods:
            assert paths[path][method]["security"] == [
                {snapshot["security_scheme"]: []}
            ]
    schema = document["components"]["schemas"][snapshot["schema"]]
    assert sorted(schema["required"]) == snapshot["required_fields"]
