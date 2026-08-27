import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiscoveryAttentionPolicy(BaseModel):
    attention_budget: int = Field(ge=1, le=10000)
    maximum_selected: int = Field(ge=1, le=100)
    minimum_distinct_domains: int = Field(ge=1, le=50)
    maximum_per_domain: int = Field(ge=1, le=20)
    maximum_per_cluster: int = Field(ge=1, le=20)
    relevance_weight: float = Field(default=0.45, ge=0, le=1)
    feasibility_weight: float = Field(default=0.35, ge=0, le=1)
    novelty_weight: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def valid_policy(self):
        if (
            abs(
                self.relevance_weight
                + self.feasibility_weight
                + self.novelty_weight
                - 1.0
            )
            > 1e-9
        ):
            raise ValueError("Scoring weights must sum to one.")
        if self.minimum_distinct_domains > self.maximum_selected:
            raise ValueError("Domain-diversity floor exceeds selected-item budget.")
        return self


class DiscoveryAttentionCandidate(BaseModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    domain_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,149}$")
    cluster_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,149}$")
    source_type: Literal[
        "curriculum_evaluation",
        "discovery_map",
        "autonomous_session",
        "mechanism_evaluation",
        "selection_bias_audit",
    ]
    source_id: uuid.UUID
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    question: str = Field(min_length=10, max_length=2000)
    decision_relevance: float = Field(ge=0, le=1)
    feasibility: float = Field(ge=0, le=1)
    attention_cost: int = Field(ge=1, le=1000)


class DiscoveryPortfolioCreate(BaseModel):
    portfolio_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    project: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=10, max_length=2000)
    source_epoch: datetime
    policy: DiscoveryAttentionPolicy
    candidates: list[DiscoveryAttentionCandidate] = Field(min_length=2, max_length=200)
    created_by: str = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def valid_candidate_family(self):
        if self.source_epoch.tzinfo is None:
            raise ValueError("source_epoch must be timezone aware.")
        keys = [item.candidate_key for item in self.candidates]
        sources = [(item.source_type, item.source_id) for item in self.candidates]
        questions = [
            " ".join(item.question.lower().split()) for item in self.candidates
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Candidate keys must be unique.")
        if len(sources) != len(set(sources)):
            raise ValueError("A canonical source may appear only once per portfolio.")
        if len(questions) != len(set(questions)):
            raise ValueError("Exact semantic question duplicates are forbidden.")
        domains = {item.domain_key for item in self.candidates}
        if len(domains) < self.policy.minimum_distinct_domains:
            raise ValueError("Candidates cannot satisfy the domain-diversity floor.")
        return self


class DiscoveryPortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    portfolio_key: str
    version: str
    project: str
    objective: str
    policy: dict
    policy_digest: str
    source_epoch: datetime
    status: str
    candidate_count: int
    selected_count: int
    attention_used: int
    allocation_digest: str
    created_by: str
    created_at: datetime
    candidates: list[dict]
    events: list[dict]
