from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCORE_THRESHOLDS = {
    "citation_entailment",
    "answer_completeness",
    "unsupported_claim_control",
    "abstention_calibration",
    "formula_accuracy",
    "table_accuracy",
    "multi_hop_validity",
    "latency_compliance",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TaskType = Literal[
    "direct_citation",
    "formula",
    "table",
    "symbol_disambiguation",
    "cross_document_synthesis",
    "contradiction",
    "temporal_supersession",
    "negative_result",
    "multi_hop",
    "no_answer",
]


class HiddenEvaluationItem(StrictModel):
    item_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)
    domain: str = Field(min_length=1, max_length=100)
    task_type: TaskType
    prompt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_citation_digests: list[str] = Field(default_factory=list)
    required_answer_tokens: list[str] = Field(default_factory=list)
    supported_claim_digests: list[str] = Field(default_factory=list)
    formula_digest: str | None = None
    table_digest: str | None = None
    path_edge_digests: list[str] = Field(default_factory=list)
    must_abstain: bool = False


class IntelligenceSuiteCreate(StrictModel):
    suite_version: str = Field(min_length=1, max_length=100)
    scope: Literal["contract_fixture", "live_corpus"]
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    projection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[HiddenEvaluationItem] = Field(min_length=1)
    thresholds: dict[str, float]
    created_by: str = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.item_key for item in self.items}) != len(self.items):
            raise ValueError("item keys must be unique")
        missing = SCORE_THRESHOLDS - self.thresholds.keys()
        if missing:
            raise ValueError(f"missing score thresholds: {', '.join(sorted(missing))}")
        invalid = {
            key: value
            for key, value in self.thresholds.items()
            if key in SCORE_THRESHOLDS and not 0 <= value <= 1
        }
        if invalid:
            raise ValueError("score thresholds must be between zero and one")
        if self.thresholds.get("maximum_latency_ms", 0) <= 0:
            raise ValueError("maximum_latency_ms must be positive")
        regression = self.thresholds.get("maximum_metric_regression", 0)
        if not 0 <= regression <= 1:
            raise ValueError("maximum_metric_regression must be between zero and one")
        return self


class IntelligenceResponse(StrictModel):
    item_key: str
    answer_tokens: list[str] = Field(default_factory=list)
    citation_digests: list[str] = Field(default_factory=list)
    claim_digests: list[str] = Field(default_factory=list)
    formula_digest: str | None = None
    table_digest: str | None = None
    path_edge_digests: list[str] = Field(default_factory=list)
    abstained: bool = False
    latency_ms: int = Field(ge=0)


class IntelligenceRunCreate(StrictModel):
    suite_id: UUID
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    projection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_runtime_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_id: str = Field(min_length=1, max_length=150)
    responses: list[IntelligenceResponse] = Field(min_length=1)
