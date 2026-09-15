import hashlib
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def review_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


class StrategyReviewVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["approve", "reject"]
    rationale: str = Field(min_length=20, max_length=4000)
    checks: list[str] = Field(min_length=1, max_length=30)
    blockers: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def no_unresolved_approval(self):
        if self.verdict == "approve" and self.blockers:
            raise ValueError("Approval cannot contain unresolved blockers")
        return self


class AlphaStrategyReviewContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Literal["bulletproof_bt"]
    workflow: Literal["alpha-strategy-review"]
    base_ref: str = Field(pattern=r"^[0-9a-f]{40}$")
    route_id: UUID
    assignment_id: UUID
    evaluator_agent_id: UUID
    evaluator_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_package_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_kind: Literal["strategy_spec", "causality_leakage"]
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    subject: dict[str, Any]
    qualification: dict[str, Any]
    max_duration_seconds: int = Field(default=900, ge=60, le=1800)
    authority: Literal["review_only_no_execution"]

    @model_validator(mode="after")
    def exact_subject(self):
        if len(json.dumps(self.model_dump(mode="json"), allow_nan=False).encode()) > 100_000:
            raise ValueError("Review context exceeds the bounded contract")
        if review_digest(self.subject) != self.subject_digest:
            raise ValueError("Review subject digest mismatch")
        if self.subject.get("source_commit") != self.base_ref:
            raise ValueError("Review source commit mismatch")
        for field, binding in (("card", "card_digest"), ("artifact_bundle", "artifact_bundle_digest")):
            if not isinstance(self.qualification.get(field), dict) or (
                review_digest(self.qualification[field]) != self.subject.get(binding)
            ):
                raise ValueError("Review artifacts differ from the routed subject")
        if str(self.evaluator_agent_id) in self.subject.get("producer_agent_ids", []):
            raise ValueError("Producer cannot review its own strategy")
        return self
