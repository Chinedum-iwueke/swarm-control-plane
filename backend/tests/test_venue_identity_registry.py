from unittest.mock import MagicMock

import pytest
from app.api.routes.venue_identities import router
from app.schemas.venue_identity import VenueIdentityCreate
from app.services.venue_identity import (
    VenueIdentityConflict,
    digest,
    register_venue_identity,
)


def specification():
    return {"schema_version": "exec003-venue-identity-v1.0.0"}


def payload(**overrides):
    values = {
        "name": "explicit-cross-venue-identity",
        "version": "1.0.0",
        "producer": "bt.institutional.venue.venue_identity_receipt",
        "source_commit": "a" * 40,
        "specification_digest": digest(specification()),
        "specification": specification(),
        "status": "active",
        "registered_by": "exec003-bootstrap",
    }
    values.update(overrides)
    return VenueIdentityCreate.model_validate(values)


def test_registers_and_replays_venue_identity_idempotently():
    db = MagicMock()
    db.scalar.return_value = None
    record = register_venue_identity(db, payload())
    assert record.specification_digest == digest(specification())
    replay = MagicMock()
    replay.scalar.return_value = record
    assert register_venue_identity(replay, payload()) is record


def test_rejects_digest_and_version_drift():
    with pytest.raises(VenueIdentityConflict, match="digest"):
        register_venue_identity(
            MagicMock(), payload(specification_digest="0" * 64)
        )
    db = MagicMock()
    db.scalar.return_value = MagicMock(specification_digest="1" * 64)
    with pytest.raises(VenueIdentityConflict, match="immutable"):
        register_venue_identity(db, payload())


def test_routes_are_orchestrator_protected():
    assert router.dependencies
    assert {route.path for route in router.routes} == {
        "/v1/research/venue-identities",
        "/v1/research/venue-identities/{identity_id}",
    }
