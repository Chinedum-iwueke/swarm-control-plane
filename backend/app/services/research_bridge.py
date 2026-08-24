from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_bridge import GovernedResearchBridge
from app.schemas.research_bridge import GovernedResearchAdvance, GovernedResearchProposal


STAGES = (
    "approved", "registry_bound", "executed", "truth_validated",
    "bundle_finalized", "independently_reviewed", "published",
    "memory_confirmed", "complete",
)
NAMESPACE = uuid.UUID("02e23374-78b8-48ae-8930-4728eae9cb73")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def create_bridge(db: Session, proposal: GovernedResearchProposal) -> GovernedResearchBridge:
    document = proposal.model_dump(mode="json")
    expected = _digest({key: value for key, value in document.items() if key not in {"proposal_digest", "state"}})
    if expected != proposal.proposal_digest:
        raise HTTPException(status_code=409, detail="Proposal digest does not match its immutable specification.")
    existing = db.scalar(select(GovernedResearchBridge).where(GovernedResearchBridge.proposal_digest == expected))
    if existing is not None:
        if existing.proposal != document:
            raise HTTPException(status_code=409, detail="Proposal digest is already bound to different content.")
        return existing
    bridge = GovernedResearchBridge(
        id=uuid.uuid5(NAMESPACE, expected), proposal_digest=expected,
        state="awaiting_approval", proposal=document, receipts={},
    )
    db.add(bridge)
    db.commit()
    db.refresh(bridge)
    return bridge


def get_bridge(db: Session, bridge_id: uuid.UUID, *, lock: bool = False) -> GovernedResearchBridge:
    query = select(GovernedResearchBridge).where(GovernedResearchBridge.id == bridge_id)
    if lock:
        query = query.with_for_update()
    bridge = db.scalar(query)
    if bridge is None:
        raise HTTPException(status_code=404, detail="Governed research bridge not found.")
    return bridge


def advance_bridge(db: Session, bridge_id: uuid.UUID, payload: GovernedResearchAdvance) -> GovernedResearchBridge:
    bridge = get_bridge(db, bridge_id, lock=True)
    if bridge.state == payload.next_state:
        if bridge.receipts.get(payload.next_state) != payload.receipt:
            raise HTTPException(status_code=409, detail="Stage receipt identity is immutable.")
        return bridge
    if bridge.state != payload.expected_state:
        raise HTTPException(status_code=409, detail=f"Bridge is {bridge.state}, expected {payload.expected_state}.")
    expected_index = -1 if payload.expected_state == "awaiting_approval" else STAGES.index(payload.expected_state)
    if payload.next_state not in STAGES or STAGES.index(payload.next_state) != expected_index + 1:
        raise HTTPException(status_code=409, detail="Bridge stages cannot be skipped or reordered.")
    if not payload.receipt:
        raise HTTPException(status_code=422, detail="A digest-bound stage receipt is required.")
    receipts = dict(bridge.receipts)
    receipts[payload.next_state] = payload.receipt
    bridge.receipts = receipts
    bridge.state = payload.next_state
    bridge.updated_at = datetime.now(UTC)
    if payload.next_state == "complete":
        bridge.completed_at = bridge.updated_at
    db.commit()
    db.refresh(bridge)
    return bridge
