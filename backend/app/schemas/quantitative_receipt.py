from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"

QuantitativeMilestone = Literal[
    "ALPHA-001",
    "DATA-001",
    "DATA-002",
    "DATA-003",
    "DISC-002",
    "DISC-003",
    "DISC-004",
    "DISC-005",
    "DISC-007",
    "EXEC-001",
    "EXEC-002",
    "EXEC-003",
    "EXEC-004",
    "EXEC-005",
    "EXEC-006",
    "ML-002",
    "ML-003",
    "ML-004",
    "PORT-002",
    "PORT-003",
    "PORT-004",
    "RL-001",
    "RL-002",
    "RISK-001",
    "RISK-002",
    "RISK-003",
    "SHADOW-002",
    "RISK-004",
    "RISK-005",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthorityBoundary(StrictModel):
    allocation: Literal[False] = False
    capital: Literal[False] = False
    orders: Literal[False] = False
    promotion: Literal[False] = False


class BulletproofProducerReceipt(StrictModel):
    schema_version: Literal["bulletproof-producer-receipt-v1.0.0"]
    milestone: QuantitativeMilestone
    producer: str = Field(min_length=1, max_length=240)
    producer_version: str = Field(pattern=_KEY, max_length=50)
    source_commit: str = Field(pattern=_COMMIT)
    input_digest: str = Field(pattern=_DIGEST)
    dataset_digest: str = Field(pattern=_DIGEST)
    configuration_digest: str = Field(pattern=_DIGEST)
    artifact_digest: str = Field(pattern=_DIGEST)
    result_digest: str = Field(pattern=_DIGEST)
    result: dict
    authority: AuthorityBoundary
    receipt_digest: str = Field(pattern=_DIGEST)


class QuantitativeReceiptCreate(StrictModel):
    receipt: BulletproofProducerReceipt
    registered_by: str = Field(pattern=_KEY, max_length=150)


class QuantitativeReceiptResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    milestone: QuantitativeMilestone
    producer: str
    producer_version: str
    source_commit: str
    dataset_digest: str
    result_digest: str
    receipt_digest: str
    receipt: dict
    registered_by: str
    registered_at: datetime
