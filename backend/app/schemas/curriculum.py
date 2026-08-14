from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurriculumTopic(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9._-]{1,99}$")
    title: str = Field(min_length=3, max_length=300)
    prerequisite_keys: list[str] = Field(default_factory=list, max_length=20)
    evidence_object_ids: list[UUID] = Field(min_length=1, max_length=500)
    source_object_ids: list[UUID] = Field(min_length=1, max_length=100)
    opposing_evidence_object_ids: list[UUID] = Field(
        default_factory=list, max_length=200
    )
    minimum_sources: int = Field(default=1, ge=1, le=100)

    @field_validator(
        "prerequisite_keys",
        "evidence_object_ids",
        "source_object_ids",
        "opposing_evidence_object_ids",
    )
    @classmethod
    def unique_values(cls, value: list) -> list:
        if len(set(value)) != len(value):
            raise ValueError("curriculum lists must not contain duplicates")
        return value


class SourceQualityRubric(StrictModel):
    allowed_authority_classes: list[
        Literal["primary", "derived", "institutional", "operational"]
    ] = Field(min_length=1, max_length=4)
    minimum_distinct_sources_per_topic: int = Field(default=1, ge=1, le=100)
    maximum_quarantined_fraction: float = Field(default=0.05, ge=0, le=1)
    require_opposing_evidence: bool = True


class DomainCurriculumCreate(StrictModel):
    domain_key: str = Field(pattern=r"^[a-z][a-z0-9._-]{1,149}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=20, max_length=4000)
    project: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    topics: list[CurriculumTopic] = Field(min_length=1, max_length=100)
    source_quality: SourceQualityRubric
    qualified_roles: list[str] = Field(min_length=1, max_length=30)
    review_cadence_days: int = Field(default=90, ge=1, le=730)
    created_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,149}$")

    @model_validator(mode="after")
    def validate_topic_graph(self) -> DomainCurriculumCreate:
        keys = [topic.key for topic in self.topics]
        if len(set(keys)) != len(keys):
            raise ValueError("curriculum topic keys must be unique")
        known = set(keys)
        for topic in self.topics:
            if topic.key in topic.prerequisite_keys:
                raise ValueError("a topic cannot require itself")
            if not set(topic.prerequisite_keys).issubset(known):
                raise ValueError("curriculum prerequisites must reference known topics")
        visiting: set[str] = set()
        visited: set[str] = set()
        graph = {topic.key: topic.prerequisite_keys for topic in self.topics}

        def visit(key: str) -> None:
            if key in visiting:
                raise ValueError("curriculum prerequisites must be acyclic")
            if key in visited:
                return
            visiting.add(key)
            for dependency in graph[key]:
                visit(dependency)
            visiting.remove(key)
            visited.add(key)

        for key in keys:
            visit(key)
        return self


class DomainCurriculumResponse(DomainCurriculumCreate):
    id: UUID
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    graph_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["draft", "qualified", "review_due", "superseded"]
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class BrainEvaluationCase(StrictModel):
    case_key: str = Field(pattern=r"^[a-z][a-z0-9._-]{1,99}$")
    query: str = Field(min_length=3, max_length=1000)
    expected_object_ids: list[UUID] = Field(default_factory=list, max_length=50)
    opposing_object_ids: list[UUID] = Field(default_factory=list, max_length=50)
    forbidden_object_ids: list[UUID] = Field(default_factory=list, max_length=50)
    should_abstain: bool = False

    @model_validator(mode="after")
    def abstention_has_no_expected_answer(self) -> BrainEvaluationCase:
        if self.should_abstain and (
            self.expected_object_ids or self.opposing_object_ids
        ):
            raise ValueError("abstention cases cannot prescribe answer evidence")
        if not self.should_abstain and not self.expected_object_ids:
            raise ValueError("answerable cases require expected evidence")
        return self


class BrainEvaluationThresholds(StrictModel):
    minimum_retrieval_recall: float = Field(default=0.8, ge=0, le=1)
    minimum_citation_fidelity: float = Field(default=1.0, ge=0, le=1)
    minimum_opposition_recall: float = Field(default=0.8, ge=0, le=1)
    minimum_abstention_accuracy: float = Field(default=1.0, ge=0, le=1)
    maximum_cross_domain_leakage: float = Field(default=0.0, ge=0, le=1)
    minimum_topic_coverage: float = Field(default=0.8, ge=0, le=1)


class BrainEvaluationCreate(StrictModel):
    curriculum_id: UUID
    evaluation_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    cases: list[BrainEvaluationCase] = Field(min_length=2, max_length=200)
    thresholds: BrainEvaluationThresholds
    evaluated_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,149}$")

    @field_validator("cases")
    @classmethod
    def unique_case_keys(
        cls, value: list[BrainEvaluationCase]
    ) -> list[BrainEvaluationCase]:
        if len({case.case_key for case in value}) != len(value):
            raise ValueError("evaluation case keys must be unique")
        if not any(case.should_abstain for case in value):
            raise ValueError("evaluation set requires an abstention case")
        return value


class BrainEvaluationResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    curriculum_id: UUID
    evaluation_version: str
    corpus_digest: str
    graph_manifest_digest: str
    evaluation_set_digest: str
    thresholds: dict
    metrics: dict
    cases: list[dict]
    passed: bool
    status: Literal["qualified", "gaps_detected"]
    review_due_days: int
    record_digest: str
    evaluated_by: str
    evaluated_at: datetime


class DomainReadinessResponse(StrictModel):
    domain_key: str
    curriculum_id: UUID
    curriculum_version: str
    curriculum_status: str
    corpus_digest: str
    graph_manifest_digest: str
    topic_count: int
    covered_topic_count: int
    topic_coverage: float
    quarantined_items: int
    evaluation: BrainEvaluationResponse | None
    ready: bool
    reasons: list[str]
