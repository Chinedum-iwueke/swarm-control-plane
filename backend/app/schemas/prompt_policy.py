import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ModelBinding(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    runtime: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=120)


class PromptPolicyBundleCreate(BaseModel):
    bundle_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    purpose: str = Field(min_length=1, max_length=2000)
    model_binding: ModelBinding
    prompt_template: str = Field(min_length=1, max_length=100000)
    policy: dict
    input_schema: dict
    output_schema: dict
    trust_labels: list[
        Literal[
            "trusted_system",
            "trusted_operator",
            "untrusted_corpus",
            "untrusted_external",
        ]
    ] = Field(min_length=1)
    allowed_tools: list[str] = Field(default_factory=list, max_length=50)
    allowed_data_classes: list[str] = Field(default_factory=list, max_length=50)
    created_by: str = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def validate_contract(self):
        for name, schema in (
            ("input", self.input_schema),
            ("output", self.output_schema),
        ):
            if schema.get("type") != "object":
                raise ValueError(f"{name}_schema must declare an object root")
            if schema.get("additionalProperties") is not False:
                raise ValueError(
                    f"{name}_schema must fail closed on additional properties"
                )
        required_policy = {
            "instruction_precedence",
            "injection_response",
            "secret_handling",
            "output_authority",
        }
        if not required_policy.issubset(self.policy):
            raise ValueError("policy is missing a required trust-boundary control")
        if self.policy.get("output_authority") != "data_only":
            raise ValueError("model output must remain data_only")
        return self


class PromptPolicyEvaluationCreate(BaseModel):
    category: Literal[
        "valid_output",
        "prompt_injection",
        "secret_exfiltration",
        "malformed_output",
        "instruction_collision",
    ]
    fixture: dict
    model_output: object
    evaluated_by: str = Field(min_length=1, max_length=150)


class PromptPolicyAction(BaseModel):
    actor: str = Field(min_length=1, max_length=150)
    reason: str = Field(min_length=1, max_length=2000)


class PromptPolicyBundleResponse(BaseModel):
    id: uuid.UUID
    bundle_key: str
    version: str
    purpose: str
    status: str
    schema_version: str
    model_binding: dict
    trust_labels: list[str]
    allowed_tools: list[str]
    allowed_data_classes: list[str]
    bundle_digest: str
    created_by: str
    created_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None
    evaluations: list[dict]
    events: list[dict]


class PromptPolicyEvaluationResponse(BaseModel):
    accepted: bool
    evaluation_id: uuid.UUID
    receipt_digest: str
    violations: list[str]
