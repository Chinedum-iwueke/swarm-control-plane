"""Frozen method-design work; readiness never implies scientific acceptance."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swarm_worker.engineering_episode import canonical_digest
from swarm_worker.method_episode import MethodEpisodePolicy, bounded


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
    evidence_catalog: dict[str, dict] = Field(min_length=1, max_length=16)
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
                   'multiplicity', 'eligibility_policy', 'undefined_replicate_policy', 'calibration', 'calibration_design'}
        if not set(self.policy.allowed_method_fields) <= allowed:
            raise ValueError('unsupported design repair scope')
        method = self.proposal['method']
        if ('experiment' in method) != ('calibration_design' in method):
            raise ValueError('Structured calibration requires both experiment and calibration_design')
        if 'calibration_design' in self.policy.allowed_method_fields and 'experiment' not in method:
            raise ValueError('Calibration design repair requires a frozen experiment')
        if (method.get('schema_version') != 'design-adequacy-contract-v1'
                or not isinstance(method.get('estimand'), str) or not method['estimand'].strip()):
            raise ValueError('frozen native design identity required')
        bounded(self.model_dump(mode='json'))
        return self
