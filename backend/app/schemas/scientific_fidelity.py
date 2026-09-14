from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParserOutput(StrictModel):
    parser: str = Field(min_length=1, max_length=100)
    method: Literal["native", "structural", "ocr", "operator"]
    content: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class SymbolDefinition(StrictModel):
    symbol: str = Field(min_length=1, max_length=40)
    definition: str = Field(min_length=1)
    scope: str = Field(min_length=1)


class UnitDefinition(StrictModel):
    symbol: str = Field(min_length=1, max_length=40)
    unit: str = Field(min_length=1, max_length=80)
    dimension: str = Field(min_length=1, max_length=80)


class ScientificRepresentationCreate(StrictModel):
    source_object_id: UUID
    representation_version: Literal[
        "scientific-fidelity-v1.0.0",
        "scientific-fidelity-v1.1.0",
        "scientific-fidelity-v2.0.0",
        "scientific-fidelity-v2.1.0",
    ] = "scientific-fidelity-v2.1.0"
    scientific_type: Literal["equation", "table", "figure"]
    source_region_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_outputs: list[ParserOutput] = Field(min_length=1)
    symbols: list[SymbolDefinition] = Field(default_factory=list)
    units: list[UnitDefinition] = Field(default_factory=list)
    table_grid: list[list[str]] | None = None
    figure_caption: str | None = None
    cross_references: list[UUID] = Field(default_factory=list)
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)

    @model_validator(mode="after")
    def require_typed_payload(self):
        if self.scientific_type == "table" and not self.table_grid:
            raise ValueError("table_grid is required for table representations")
        if self.scientific_type == "figure" and not self.figure_caption:
            raise ValueError("figure_caption is required for figure representations")
        return self


class ScientificRepresentationResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_object_id: UUID
    representation_version: str
    scientific_type: str
    status: str
    normalized_content: str
    semantic_payload: dict
    parser_outputs: list
    uncertainties: list
    source_region_digest: str
    record_digest: str
    created_by: str
    created_at: datetime


class FidelityManifestCreate(StrictModel):
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    representation_version: Literal[
        "scientific-fidelity-v1.0.0",
        "scientific-fidelity-v1.1.0",
        "scientific-fidelity-v2.0.0",
        "scientific-fidelity-v2.1.0",
    ] = "scientific-fidelity-v2.1.0"
    thresholds: dict[str, float]
    metrics: dict[str, float]
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class FidelityManifestResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    corpus_digest: str
    representation_version: str
    status: str
    thresholds: dict
    metrics: dict
    counts: dict
    representation_digests: list
    record_digest: str
    created_by: str
    created_at: datetime


AdjudicationDecision = Literal[
    "equivalent",
    "material_mismatch",
    "wrong_object_class",
    "incomplete_region",
    "unsupported_notation",
    "unreadable_source",
]


class ScientificAdjudicationCreate(StrictModel):
    representation_id: UUID
    reviewer_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)
    reviewer_role: Literal[
        "independent_evaluator", "founder_operator", "domain_specialist"
    ]
    decision: AdjudicationDecision
    rationale: str = Field(min_length=10)
    gold_payload: dict = Field(default_factory=dict)
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScientificAdjudicationResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    representation_id: UUID
    reviewer_id: str
    reviewer_role: str
    decision: str
    rationale: str
    gold_payload: dict
    corpus_digest: str
    source_region_digest: str
    independent_of_producer: bool
    record_digest: str
    created_at: datetime


class ScientificBenchmarkCreate(StrictModel):
    benchmark_version: str = Field(min_length=1, max_length=80)
    representation_version: str = Field(min_length=1, max_length=80)
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_seed: str = Field(min_length=1, max_length=100)
    per_type: dict[Literal["equation", "table", "figure"], int]
    thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "class_precision": 0.98,
            "class_recall": 0.98,
            "coverage": 1.0,
            "escape_rate": 0.0,
        }
    )
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)

    @model_validator(mode="after")
    def require_positive_strata(self):
        if not self.per_type or any(value < 1 for value in self.per_type.values()):
            raise ValueError(
                "Each declared scientific benchmark stratum must be positive"
            )
        return self


class ScientificBenchmarkResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    benchmark_version: str
    representation_version: str
    corpus_digest: str
    sample_seed: str
    sample_spec: dict
    sampled_representation_ids: list
    sample_digest: str
    status: str
    metrics: dict
    confidence_intervals: dict
    counts: dict
    adjudication_digests: list
    record_digest: str
    evaluation_digest: str | None
    created_by: str
    created_at: datetime


class ScientificCorrectionCreate(StrictModel):
    adjudication_id: UUID
    proposed_version: str = Field(min_length=1, max_length=80)
    proposed_payload: dict
    proposer_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class ScientificCorrectionResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    representation_id: UUID
    adjudication_id: UUID
    proposed_version: str
    proposed_payload: dict
    status: str
    proposer_id: str
    record_digest: str
    created_at: datetime


class MathematicsSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    scientific_types: list[Literal["equation", "table", "figure"]] = Field(
        default_factory=list
    )
    dimensions: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=20, ge=1, le=100)


class MathematicsContextPackRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    representation_ids: list[UUID] = Field(min_length=1, max_length=50)
    created_by: str = Field(
        default="research-intelligence", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )


class ScientificCalculationCreate(StrictModel):
    representation_id: UUID
    context_pack_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    assurance_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    substitutions: dict[str, float]
    executed_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class ScientificCalculationResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    representation_id: UUID
    context_pack_digest: str
    assurance_receipt_digest: str
    expression_tree: dict
    substitutions: dict
    units: list
    result: dict
    representation_digest: str
    record_digest: str
    executed_by: str
    created_at: datetime


class MathematicsCapabilityCreate(StrictModel):
    agent_role: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$", max_length=100)
    profile_version: str = Field(min_length=1, max_length=80)
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    representation_version: str = Field(min_length=1, max_length=80)
    demonstrated_tasks: list[str] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    metrics: dict[str, float]
    thresholds: dict[str, float]
    evaluated_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class MathematicsCapabilityResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    agent_role: str
    profile_version: str
    corpus_digest: str
    representation_version: str
    demonstrated_tasks: list
    limitations: list
    metrics: dict
    status: str
    record_digest: str
    evaluated_by: str
    created_at: datetime


AssuranceLevel = Literal["machine_verified", "independently_verified"]


class ScientificAssuranceRequestCreate(StrictModel):
    representation_id: UUID
    expression: str = Field(min_length=1, max_length=4000)
    purpose: str = Field(min_length=10, max_length=2000)
    required_level: AssuranceLevel = "machine_verified"
    policy_version: str = Field(
        default="ri014d-assurance-v1.0.0", min_length=1, max_length=80
    )
    requested_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class ScientificAssuranceRequestResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    representation_id: UUID
    expression: str
    expression_digest: str
    purpose: str
    required_level: str
    policy_version: str
    status: str
    cache_key: str
    requested_by: str
    created_at: datetime


class ScientificAssuranceAttemptCreate(StrictModel):
    provider_family: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=100
    )
    extractor_version: str = Field(min_length=1, max_length=100)
    produced_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)
    independence_receipt_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    independent_review_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    content: str = Field(min_length=1, max_length=8000)
    semantic_payload: dict = Field(default_factory=dict)


class ScientificAssuranceAttemptResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_id: UUID
    provider_family: str
    extractor_version: str
    produced_by: str
    independence_receipt_digest: str | None
    independent_review_digest: str | None
    independent_of_representation: bool
    content: str
    semantic_payload: dict
    checks: dict
    outcome: str
    attempt_digest: str
    created_at: datetime


class ScientificAssuranceReceiptResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_id: UUID
    representation_id: UUID
    source_object_id: UUID
    source_content_digest: str
    source_region_digest: str
    expression_digest: str
    assurance_level: str
    status: str
    deterministic_checks: dict
    attempt_digests: list
    limitations: list
    claim_boundary: str
    record_digest: str
    issued_by: str
    created_at: datetime
