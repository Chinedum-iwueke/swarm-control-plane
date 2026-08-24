import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.research_bridge import GovernedResearchAdvance, GovernedResearchProposal
from app.services.research_bridge import advance_bridge, create_bridge


def proposal(**changes) -> GovernedResearchProposal:
    core = {
        "schema_version": "governed-research-bridge-v1.0.0",
        "authority": {
            "capital": "prohibited", "live_orders": "prohibited",
            "self_approval": "prohibited", "production_promotion": "prohibited",
        },
        "source": {"original_text": "Run bounded CSI research."},
        "resolution": {"tier": "Tier2B", "strategy_identity": "l7_h1_csi_gated_displacement_trend"},
        "dataset": {"snapshot_id": "snapshot", "digest": "a" * 64},
        "search": {"stopping_rule": "exhaustive", "variant_count": 16, "max_variants": 16},
        "required_gates": ["founder_specification_approval", "native_classic_execution"],
    }
    core.update(changes)
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()
    return GovernedResearchProposal.model_validate(core | {"state": "awaiting_approval", "proposal_digest": digest})


def test_proposal_rejects_authority_and_search_expansion() -> None:
    with pytest.raises(ValidationError):
        proposal(authority={"capital": "prohibited"})
    with pytest.raises(ValidationError):
        proposal(search={"stopping_rule": "exhaustive", "variant_count": 17, "max_variants": 16})


def test_create_is_digest_bound_and_idempotent() -> None:
    payload = proposal()
    db = MagicMock()
    db.scalar.return_value = None
    db.refresh.side_effect = lambda value: None
    created = create_bridge(db, payload)
    assert created.proposal_digest == payload.proposal_digest
    assert created.state == "awaiting_approval"
    db.scalar.return_value = created
    assert create_bridge(db, payload) is created
    tampered = payload.model_copy(update={"proposal_digest": "0" * 64})
    with pytest.raises(HTTPException, match="digest"):
        create_bridge(MagicMock(), tampered)


def test_stages_are_monotone_idempotent_and_receipts_immutable() -> None:
    bridge = SimpleNamespace(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        state="awaiting_approval", receipts={}, updated_at=None, completed_at=None,
    )
    db = MagicMock()
    db.refresh.side_effect = lambda value: None
    approved = GovernedResearchAdvance(
        expected_state="awaiting_approval", next_state="approved",
        receipt={"approval_digest": "a" * 64},
    )
    with patch("app.services.research_bridge.get_bridge", return_value=bridge):
        assert advance_bridge(db, bridge.id, approved).state == "approved"
        assert advance_bridge(db, bridge.id, approved).state == "approved"
        changed = approved.model_copy(update={"receipt": {"approval_digest": "b" * 64}})
        with pytest.raises(HTTPException, match="immutable"):
            advance_bridge(db, bridge.id, changed)
        with pytest.raises(HTTPException, match="skipped"):
            advance_bridge(db, bridge.id, GovernedResearchAdvance(
                expected_state="approved", next_state="executed", receipt={"run": "c" * 64}
            ))
