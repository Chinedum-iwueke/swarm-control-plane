"""Bounded review dispute decisions. Recheck is never scientific acceptance."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class MethodAdjudication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packet_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviews_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["repair", "recheck", "disputed"]
    finding_evidence: dict[str, list[str]] = Field(min_length=1, max_length=32)
    rationale: str = Field(min_length=20, max_length=4000)


def validate_adjudication(review, bundle, digest):
    packet, reviews = bundle["method_review_packet"], bundle["rejected_reviews"]
    decision = review.method_adjudication
    findings = {digest(f): f for r in reviews for f in r["method_verdict"]["findings"]}
    if (not findings or decision.packet_digest != digest(packet)
            or decision.reviews_digest != digest(reviews)
            or set(decision.finding_evidence) != set(findings)
            or review.verdict != "reject"):
        raise ValueError("Adjudication must cover exact rejected findings without approval")
    evidence = packet["evidence"]
    if any(digest(value) != key for key, value in evidence.items()):
        raise ValueError("Adjudication evidence digest mismatch")
    for refs in decision.finding_evidence.values():
        if not refs or len(refs) > 16 or len(refs) != len(set(refs)) or not set(refs) <= set(evidence):
            raise ValueError("Adjudication must cite retained evidence for every finding")

