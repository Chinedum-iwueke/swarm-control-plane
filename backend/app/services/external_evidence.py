from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ingestion.pipeline import contains_instruction_injection


class ExternalEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal[
        "scholarly_metadata",
        "public_transcript",
        "podcast_feed",
        "social_observation",
    ]
    canonical_url: str = Field(min_length=1, max_length=2000)
    title: str = Field(min_length=1, max_length=1000)
    content: str = Field(min_length=1, max_length=200_000)
    fetched_at: datetime
    connector: str = Field(min_length=1, max_length=100)
    provider_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    rights: str = Field(min_length=1, max_length=500)
    allowed_hosts: list[str] = Field(min_length=1, max_length=20)
    authentication_mode: Literal["public_none"] = "public_none"
    cookies_used: Literal[False] = False
    executable_content: Literal[False] = False

    @model_validator(mode="after")
    def enforce_public_allowlisted_source(self) -> ExternalEvidenceRequest:
        parsed = urlparse(self.canonical_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("external evidence requires an HTTPS canonical URL")
        if parsed.hostname not in self.allowed_hosts:
            raise ValueError("external evidence host must be explicitly allowlisted")
        return self


class ExternalEvidenceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal["admit_candidate", "observation_only", "quarantine"]
    trust_class: Literal["metadata", "transcript", "observation"]
    scientific_authority: Literal[False] = False
    execution_authority: Literal[False] = False
    source_replay_required: bool
    reasons: list[str]


def assess_external_evidence(
    request: ExternalEvidenceRequest,
) -> ExternalEvidenceDecision:
    """Classify retrieved content before it can enter canonical research evidence."""
    digest = hashlib.sha256(request.content.encode("utf-8")).hexdigest()
    if contains_instruction_injection(f"{request.title}\n{request.content}"):
        return ExternalEvidenceDecision(
            content_digest=digest,
            disposition="quarantine",
            trust_class=_trust_class(request.source_kind),
            source_replay_required=True,
            reasons=["instruction_like_content_detected"],
        )
    if request.source_kind == "social_observation":
        return ExternalEvidenceDecision(
            content_digest=digest,
            disposition="observation_only",
            trust_class="observation",
            source_replay_required=True,
            reasons=[
                "social_content_may_seed_questions_but_cannot_support_claims"
            ],
        )
    return ExternalEvidenceDecision(
        content_digest=digest,
        disposition="admit_candidate",
        trust_class=_trust_class(request.source_kind),
        source_replay_required=True,
        reasons=["independent_canonical_admission_still_required"],
    )


def _trust_class(
    source_kind: str,
) -> Literal["metadata", "transcript", "observation"]:
    if source_kind == "scholarly_metadata":
        return "metadata"
    if source_kind in {"public_transcript", "podcast_feed"}:
        return "transcript"
    return "observation"
