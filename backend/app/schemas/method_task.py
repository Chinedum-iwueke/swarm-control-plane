"""Frozen method-design work; readiness never implies scientific acceptance."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.graph import digest_document as canonical_digest
from pydantic import field_validator
import json


def bounded(value, maximum=262144):
    if len(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()) > maximum:
        raise ValueError('method contract exceeds bound')


class MethodEpisodePolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: Literal[1] = 1
    max_repairs: int = Field(default=2, ge=0, le=4)
    max_model_calls: int = Field(default=3, ge=0, le=8)
    max_tool_calls: int = Field(default=4, ge=1, le=12)
    max_work_units: int = Field(default=1000000, ge=1, le=10000000)
    tool_work_limit: int = Field(default=250000, ge=1, le=10000000)
    max_duration_seconds: int = Field(default=1800, ge=1, le=7200)
    max_context_bytes: int = Field(default=48000, ge=1024, le=128000)
    allowed_method_fields: list[str] = Field(min_length=1, max_length=20)

    @field_validator('allowed_method_fields')
    @classmethod
    def fields(cls, values):
        if len(values) != len(set(values)) or any(not v.isidentifier() for v in values):
            raise ValueError('unique explicit method fields required')
        return values


class MethodTaskContract(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repository: Literal['bulletproof_bt']
    workflow: Literal['alpha-method-design']
    base_ref: str = Field(pattern=r'^[a-f0-9]{40}$')
    candidate_id: UUID
    candidate_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    mandate_id: UUID
    mandate_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    valid_until: datetime
    proposal: dict
    requirements: dict[str, str] = Field(min_length=1, max_length=64)
    evidence_catalog: dict[str, dict] = Field(min_length=1, max_length=64)
    dependencies: dict[str, str] = Field(min_length=1, max_length=32)
    findings_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    policy: MethodEpisodePolicy
    diagnostic: Literal['design_adequacy_v1']
    authority: Literal['method_design_no_execution']

    @model_validator(mode='after')
    def exact(self):
        if self.valid_until.tzinfo is None:
            raise ValueError('timezone-aware authority expiry required')
        if set(self.proposal) != {'scientific_identity', 'support_minima', 'method'}:
            raise ValueError('frozen scientific identity and support minima required')
        if any(not isinstance(v, dict) for v in self.proposal.values()):
            raise ValueError('proposal sections must be objects')
        if any(canonical_digest(v) != k for k, v in self.evidence_catalog.items()):
            raise ValueError('evidence catalog digest mismatch')
        import re
        if any(not re.fullmatch('[a-f0-9]{64}', v) for v in self.dependencies.values()):
            raise ValueError('dependencies must be immutable digests')
        # The estimand belongs to the frozen question, not to method repair.
        allowed = {'estimator_id', 'meaningful_effect', 'dependence_assumptions',
                   'multiplicity', 'eligibility_policy', 'undefined_replicate_policy', 'calibration', 'calibration_design', 'assurance'}
        if not set(self.policy.allowed_method_fields) <= allowed:
            raise ValueError('unsupported design repair scope')
        method = self.proposal['method']
        if ('experiment' in method) != ('calibration_design' in method):
            raise ValueError('Structured calibration requires both experiment and calibration_design')
        if 'calibration_design' in self.policy.allowed_method_fields and 'experiment' not in method:
            raise ValueError('Calibration design repair requires a frozen experiment')
        if (method.get('schema_version') not in {'design-adequacy-contract-v1', 'design-adequacy-contract-v2'}
                or not isinstance(method.get('estimand'), str) or not method['estimand'].strip()):
            raise ValueError('frozen native design identity required')
        if method['schema_version'] == 'design-adequacy-contract-v2':
            assurance = method.get('assurance', {})
            if (not isinstance(assurance, dict) or not assurance.get('required_outputs')
                    or not isinstance(assurance.get('workload'), dict)
                    or not assurance['workload'].get('caps') or 'experiment' not in method):
                raise ValueError('V2 requires frozen output obligations, resource caps and experiment')
            outputs, caps = assurance['required_outputs'], assurance['workload']['caps']
            if (not isinstance(outputs, list) or not 1 <= len(outputs) <= 128
                    or any(not isinstance(v, str) or not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]{0,79}', v) for v in outputs)
                    or len(set(outputs)) != len(outputs)
                    or not isinstance(caps, dict) or not 1 <= len(caps) <= 16
                    or any(not isinstance(k, str) or not re.fullmatch('[a-z][a-z0-9_]{0,79}', k)
                           or type(v) is not int or not 1 <= v <= 10**15 for k, v in caps.items())
                    or not isinstance(method.get('calibration'), dict)
                    or type(method['calibration'].get('max_work_units')) is not int
                    or caps.get('statistic_evaluation') != method['calibration']['max_work_units']):
                raise ValueError('Invalid frozen assurance outputs or resource caps')
        elif 'assurance' in method or 'assurance' in self.policy.allowed_method_fields:
            raise ValueError('Assurance requires an explicitly approved V2 successor')
        bounded(self.proposal)
        for document in self.evidence_catalog.values():
            bounded(document)
        bounded(self.model_dump(mode='json'), 524288)
        return self
