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
    representation_version: Literal["scientific-fidelity-v1.0.0"] = (
        "scientific-fidelity-v1.0.0"
    )
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
    representation_version: Literal["scientific-fidelity-v1.0.0"] = (
        "scientific-fidelity-v1.0.0"
    )
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
