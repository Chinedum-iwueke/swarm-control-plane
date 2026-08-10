from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z][a-z0-9._-]{0,99}$"

EvidenceObjectType = Literal[
    "source",
    "edition",
    "artifact",
    "scientific_object",
    "claim",
    "method",
    "assumption",
    "dataset",
    "run",
    "review",
    "decision",
    "belief",
    "episode",
]
AccessClass = Literal["public", "internal", "restricted", "protected"]
AuthorityClass = Literal["primary", "derived", "institutional", "operational"]
Sha256 = Annotated[str, Field(pattern=_DIGEST)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProducerIdentity(StrictModel):
    system: str = Field(pattern=_NAME)
    native_type: str = Field(pattern=_NAME)
    native_id: str = Field(min_length=1, max_length=300)
    schema_version: str = Field(min_length=1, max_length=150)


class EvidenceAlias(StrictModel):
    namespace: str = Field(pattern=_NAME)
    object_type: str = Field(pattern=_NAME)
    value: str = Field(min_length=1, max_length=300)


class SourcePayload(StrictModel):
    kind: Literal["source"]
    title: str = Field(min_length=1, max_length=500)
    origin: str = Field(min_length=1, max_length=2000)
    rights: str = Field(min_length=1, max_length=500)
    acquired_at: datetime


class EditionPayload(StrictModel):
    kind: Literal["edition"]
    source_object_id: UUID
    edition_label: str = Field(min_length=1, max_length=300)
    published_at: datetime | None = None


class ArtifactPayload(StrictModel):
    kind: Literal["artifact"]
    edition_object_id: UUID
    media_type: str = Field(min_length=1, max_length=200)
    storage_uri: str = Field(min_length=1, max_length=1000)
    byte_size: int = Field(ge=0)
    artifact_digest: str = Field(pattern=_DIGEST)


class ScientificObjectPayload(StrictModel):
    kind: Literal["scientific_object"]
    artifact_object_id: UUID
    scientific_type: Literal[
        "section", "paragraph", "table", "figure", "equation", "citation", "note"
    ]
    parent_object_id: UUID | None = None
    coordinates: dict[str, int | float | str]
    extraction_method: str = Field(min_length=1, max_length=300)
    extraction_confidence: float = Field(ge=0, le=1)
    content_text: str | None = Field(default=None, min_length=1, max_length=100_000)


class ClaimPayload(StrictModel):
    kind: Literal["claim"]
    proposition: str = Field(min_length=1, max_length=10_000)
    evidence_object_ids: list[UUID] = Field(min_length=1, max_length=100)
    qualifiers: list[str] = Field(default_factory=list, max_length=50)
    status: Literal["proposed", "supported", "disputed", "invalidated", "retired"]


class MethodPayload(StrictModel):
    kind: Literal["method"]
    name: str = Field(min_length=1, max_length=500)
    procedure: str = Field(min_length=1, max_length=20_000)
    evidence_object_ids: list[UUID] = Field(min_length=1, max_length=100)
    assumption_object_ids: list[UUID] = Field(default_factory=list, max_length=100)


class AssumptionPayload(StrictModel):
    kind: Literal["assumption"]
    statement: str = Field(min_length=1, max_length=10_000)
    scope: str = Field(min_length=1, max_length=2000)
    evidence_object_ids: list[UUID] = Field(default_factory=list, max_length=100)


class DatasetPayload(StrictModel):
    kind: Literal["dataset"]
    source_object_ids: list[UUID] = Field(min_length=1, max_length=100)
    schema_digest: str = Field(pattern=_DIGEST)
    partition_digests: list[Sha256] = Field(min_length=1, max_length=10_000)
    availability_policy: str = Field(min_length=1, max_length=2000)
    correction_object_ids: list[UUID] = Field(default_factory=list, max_length=100)


class RunPayload(StrictModel):
    kind: Literal["run"]
    dataset_object_ids: list[UUID] = Field(min_length=1, max_length=100)
    specification_digest: str = Field(pattern=_DIGEST)
    code_digest: str = Field(pattern=_DIGEST)
    environment_digest: str = Field(pattern=_DIGEST)
    attempt: int = Field(ge=1)


class ReviewPayload(StrictModel):
    kind: Literal["review"]
    subject_object_id: UUID
    subject_digest: str = Field(pattern=_DIGEST)
    reviewer_authority: str = Field(pattern=_NAME)
    verdict: Literal["approved", "rejected", "needs_changes", "inconclusive"]
    rationale: str = Field(min_length=1, max_length=10_000)


class DecisionPayload(StrictModel):
    kind: Literal["decision"]
    evidence_object_ids: list[UUID] = Field(min_length=1, max_length=100)
    decided_by_authority: str = Field(pattern=_NAME)
    decision: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=10_000)
    valid_from: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validity_is_ordered(self) -> DecisionPayload:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class BeliefPayload(StrictModel):
    kind: Literal["belief"]
    claim_object_id: UUID
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    opposing_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    assessment: str = Field(min_length=1, max_length=10_000)
    confidence: float = Field(ge=0, le=1)
    owner: str = Field(pattern=_NAME)
    reviewers: list[str] = Field(min_length=1, max_length=20)
    valid_from: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validity_is_ordered(self) -> BeliefPayload:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class EpisodePayload(StrictModel):
    kind: Literal["episode"]
    task_id: UUID | None = None
    input_object_ids: list[UUID] = Field(default_factory=list, max_length=200)
    output_object_ids: list[UUID] = Field(default_factory=list, max_length=200)
    tools: list[str] = Field(default_factory=list, max_length=100)
    failures: list[str] = Field(default_factory=list, max_length=100)
    decision_object_ids: list[UUID] = Field(default_factory=list, max_length=100)
    lessons: list[str] = Field(default_factory=list, max_length=100)
    protected_references: list[str] = Field(default_factory=list, max_length=100)


EvidencePayload = Annotated[
    SourcePayload
    | EditionPayload
    | ArtifactPayload
    | ScientificObjectPayload
    | ClaimPayload
    | MethodPayload
    | AssumptionPayload
    | DatasetPayload
    | RunPayload
    | ReviewPayload
    | DecisionPayload
    | BeliefPayload
    | EpisodePayload,
    Field(discriminator="kind"),
]


class EvidenceObjectCreate(StrictModel):
    schema_version: str = Field(pattern=r"^canonical-identity-v1\.[0-9]+\.[0-9]+$")
    object_schema_version: str = Field(
        pattern=r"^canonical-evidence-v1\.[0-9]+\.[0-9]+$"
    )
    object_id: UUID
    object_type: EvidenceObjectType
    content_version: str = Field(min_length=1, max_length=150)
    content_digest: str = Field(pattern=_DIGEST)
    producer: ProducerIdentity
    aliases: list[EvidenceAlias] = Field(min_length=1, max_length=100)
    supersedes_object_id: UUID | None = None
    project: str = Field(pattern=_NAME)
    access_class: AccessClass
    authority_class: AuthorityClass
    payload: EvidencePayload
    created_by: str = Field(pattern=_NAME)

    @model_validator(mode="after")
    def identity_and_payload_are_consistent(self) -> EvidenceObjectCreate:
        if self.payload.kind != self.object_type:
            raise ValueError("payload kind must match object_type")
        if self.producer.native_type != self.object_type:
            raise ValueError("producer native_type must match object_type")
        producer_alias = (
            self.producer.system,
            self.producer.native_type,
            self.producer.native_id,
        )
        aliases = {(item.namespace, item.object_type, item.value) for item in self.aliases}
        if len(aliases) != len(self.aliases):
            raise ValueError("aliases must be unique")
        if producer_alias not in aliases:
            raise ValueError("producer native identity must be an alias")
        if (
            isinstance(self.payload, ArtifactPayload)
            and self.payload.artifact_digest != self.content_digest
        ):
            raise ValueError("artifact digest must match content_digest")
        expected_authority = {
            "source": {"primary"},
            "edition": {"primary"},
            "artifact": {"primary"},
            "scientific_object": {"derived"},
            "claim": {"derived"},
            "method": {"derived"},
            "assumption": {"derived"},
            "dataset": {"primary", "derived"},
            "run": {"operational"},
            "review": {"institutional"},
            "decision": {"institutional"},
            "belief": {"institutional"},
            "episode": {"operational"},
        }[self.object_type]
        if self.authority_class not in expected_authority:
            raise ValueError("authority_class is incompatible with object_type")
        return self


class EvidenceObjectResponse(EvidenceObjectCreate):
    created_at: datetime


class EvidenceLineageResponse(StrictModel):
    object: EvidenceObjectResponse
    ancestors: list[EvidenceObjectResponse]
    descendants: list[EvidenceObjectResponse]


class EvidenceObjectListResponse(StrictModel):
    items: list[EvidenceObjectResponse]
    count: int
