import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleBinding(StrictModel):
    role: str = Field(pattern=r"^[a-z][a-z0-9-]{1,79}$")
    actors: list[str] = Field(min_length=1, max_length=100)


class SeparationRule(StrictModel):
    field: Literal["requester", "originator", "evaluator"]
    minimum_risk: int = Field(ge=0, le=3)
    rule_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,119}$")


class DecisionRight(StrictModel):
    decision_type: str = Field(pattern=r"^[a-z][a-z0-9-]{1,99}$")
    actions: list[str] = Field(min_length=1, max_length=20)
    accountable_roles: list[str] = Field(min_length=1, max_length=20)
    veto_roles: list[str] = Field(default_factory=list, max_length=20)
    environments: list[str] = Field(default_factory=lambda: ["*"], min_length=1)
    maximum_risk: int = Field(ge=0, le=3)
    delegable: bool
    constitutional: bool = False
    separation: list[SeparationRule] = Field(default_factory=list, max_length=10)


class AuthorityPolicyManifest(StrictModel):
    schema_version: Literal["authority-policy-v1.0.0"]
    policy_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,99}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    roles: list[RoleBinding] = Field(min_length=1, max_length=100)
    identity_aliases: dict[str, str] = Field(default_factory=dict)
    decisions: list[DecisionRight] = Field(min_length=1, max_length=100)
    constitutional_boundaries: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_keys(self):
        if len({item.role for item in self.roles}) != len(self.roles):
            raise ValueError("role bindings must be unique")
        if len({item.decision_type for item in self.decisions}) != len(self.decisions):
            raise ValueError("decision rights must be unique")
        known = {item.role for item in self.roles}
        referenced = {role for item in self.decisions for role in item.accountable_roles + item.veto_roles}
        if not referenced <= known:
            raise ValueError("decision rights reference unknown roles")
        known_actors = {actor for item in self.roles for actor in item.actors}
        if not set(self.identity_aliases.values()) <= known_actors:
            raise ValueError("identity aliases reference unknown principals")
        return self


class AuthorityPolicyCreate(StrictModel):
    manifest: AuthorityPolicyManifest
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=2, max_length=150)


class AuthorityPolicyActivation(StrictModel):
    actor: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=10, max_length=1000)


class AuthorityResolutionRequest(StrictModel):
    actor: str = Field(min_length=2, max_length=150)
    decision_type: str
    action: str
    object_type: str
    object_id: str
    object_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: dict = Field(default_factory=dict)
    risk_level: int = Field(ge=0, le=3)
    environment: str = "internal"
    requester: str | None = None
    originator: str | None = None
    evaluator: str | None = None
    active_veto_roles: list[str] = Field(default_factory=list)
    exception_id: uuid.UUID | None = None


class DelegationCreate(StrictModel):
    grantor_actor: str
    grantee_actor: str
    decision_types: list[str] = Field(min_length=1, max_length=20)
    scope: dict = Field(default_factory=dict)
    max_risk: int = Field(ge=0, le=3)
    environment: str = "internal"
    reason: str = Field(min_length=10, max_length=1000)
    expires_at: datetime


class ExceptionCreate(StrictModel):
    rule_key: str
    requester: str
    independent_reviewer: str
    reason: str = Field(min_length=20, max_length=2000)
    scope: dict
    risk_level: int = Field(ge=0, le=3)
    compensating_controls: list[str] = Field(min_length=1, max_length=20)
    expires_at: datetime


class ExceptionDecision(StrictModel):
    actor: str
    action: Literal["approve", "reject", "close"]
    reason: str = Field(min_length=10, max_length=2000)
