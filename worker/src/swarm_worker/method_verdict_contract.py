"""Exact method verdicts; legacy strategy review serialization stays unchanged."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MethodFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: str = Field(min_length=1, max_length=200)
    evidence_digests: list[str] = Field(min_length=1, max_length=16)
    violation: str = Field(min_length=1, max_length=4000)
    verification: str = Field(min_length=1, max_length=2000)


class MethodVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packet_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    verdict: Literal["accept", "reject"]
    checks: list[str] = Field(min_length=1, max_length=64)
    findings: list[MethodFinding] = Field(max_length=32)
    rationale: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def consistent(self):
        if (self.verdict == "accept") == bool(self.findings):
            raise ValueError("acceptance must have no findings; rejection needs findings")
        return self


def validate_method_review(review, packet, digest):
    """Checks custody and explicit obligations, not scientific truth."""
    verdict = review.method_verdict
    if verdict.packet_digest != digest(packet):
        raise ValueError("Method verdict identifies a different packet")
    if len(verdict.checks) != len(set(verdict.checks)) or set(verdict.checks) != set(packet["requirements"]):
        raise ValueError("Method review must check every exact requirement once")
    if (review.verdict == "approve") != (verdict.verdict == "accept"):
        raise ValueError("Outer and method verdicts disagree")
    if review.blockers != [finding.violation for finding in verdict.findings]:
        raise ValueError("Method blockers differ from retained findings")
    evidence = packet["evidence"]
    if not evidence or any(digest(value) != key for key, value in evidence.items()):
        raise ValueError("Method evidence digest mismatch")
    for finding in verdict.findings:
        if finding.criterion not in packet["requirements"] or any(key not in evidence for key in finding.evidence_digests):
            raise ValueError("Method finding must identify a recorded criterion and evidence")


def complete_rejection_summary(review):
    """Only add verbatim detailed findings; never erase a blocker or change a verdict."""
    findings = [finding.violation for finding in review.method_verdict.findings]
    if review.blockers == findings:
        return review
    if (review.verdict != 'reject' or review.method_verdict.verdict != 'reject'
            or len(findings) > 30 or len(set(review.blockers)) != len(review.blockers)
            or any(blocker not in findings for blocker in review.blockers)):
        raise ValueError('Review summary cannot be completed without changing meaning')
    return type(review).model_validate(review.model_dump() | {'blockers': findings})

