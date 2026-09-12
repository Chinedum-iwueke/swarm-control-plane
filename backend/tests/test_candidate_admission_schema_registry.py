from unittest.mock import MagicMock

import pytest
from app.api.routes.candidate_admission_schemas import router
from app.schemas.candidate_admission_schema import CandidateAdmissionSchemaCreate
from app.services.candidate_admission_schema import (
    CandidateAdmissionSchemaConflict,
    digest,
    register_candidate_admission_schema,
)


def specification():
    return {"schema_version": "risk004-candidate-admission-v1.0.0"}


def payload(**updates):
    values = {
        "name": "candidate-admission",
        "version": "1.0.0",
        "producer": "bt.institutional.candidate_admission.candidate_admission_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "risk004-pilot",
    }
    values.update(updates)
    return CandidateAdmissionSchemaCreate.model_validate(values)


def test_registers_idempotently_and_rejects_drift():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_candidate_admission_schema(db, payload())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_candidate_admission_schema(replay, payload()) is record
    with pytest.raises(CandidateAdmissionSchemaConflict):
        register_candidate_admission_schema(
            MagicMock(), payload(specification_digest="0" * 64)
        )


def test_routes_are_protected():
    assert router.dependencies
    assert len(router.routes) == 3
