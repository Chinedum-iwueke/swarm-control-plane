"""Compare frozen and released representation documents without rebinding either.

This is diagnostic evidence for an execution-handoff reviewer, not approval or a
replacement for the native full-document identity checks.
"""
from copy import deepcopy
import json
import re

from app.schemas.alpha_discovery import (
    AlphaRepresentationBasketMember,
    AlphaRepresentationTransformation,
)
from app.schemas.method_task import canonical_digest


_FIELDS = {
    'schema_version', 'candidate_key', 'instruments', 'basket_members',
    'source_timeframe', 'research_timeframe', 'resampling_policy', 'transformations',
    'transformation_rationale', 'rejected_alternatives', 'selection_data_boundary',
    'outcome_data_consulted',
}


def _projection(document):
    if not isinstance(document, dict) or set(document) != _FIELDS:
        raise ValueError('Representation document fields are not exact')
    # Reject non-JSON/non-finite inputs rather than normalizing identity-bearing data.
    json.dumps(document, allow_nan=False)
    if (document['schema_version'] != 'adaptive-representation-plan-v1.0.0'
            or document['source_timeframe'] != '1m'
            or document['resampling_policy'] != 'left_closed_left_labeled_complete_bars'
            or document['selection_data_boundary'] != 'metadata_predictors_only_no_targets'
            or document['outcome_data_consulted'] is not False):
        raise ValueError('Representation boundary is unsupported or unsafe')
    if (not isinstance(document['candidate_key'], str) or not document['candidate_key']
            or not isinstance(document['research_timeframe'], str)
            or not re.fullmatch(r'[1-9][0-9]*[mhd]', document['research_timeframe'])):
        raise ValueError('Representation identity or clock is invalid')
    members, transforms = document['basket_members'], document['transformations']
    if (not isinstance(members, list) or not 1 <= len(members) <= 128
            or not isinstance(transforms, list) or not 1 <= len(transforms) <= 256):
        raise ValueError('Representation member/operator bounds are invalid')
    for member in members:
        AlphaRepresentationBasketMember.model_validate(member)
    for transform in transforms:
        AlphaRepresentationTransformation.model_validate(transform)
    instruments = [member['instrument'] for member in members]
    outputs = [transform['output_field'] for transform in transforms]
    if (instruments != document['instruments'] or len(set(instruments)) != len(instruments)
            or len(set(outputs)) != len(outputs)):
        raise ValueError('Representation members or outputs are ambiguous')
    if (not isinstance(document['transformation_rationale'], str)
            or not document['transformation_rationale'].strip()
            or not isinstance(document['rejected_alternatives'], list)
            or not document['rejected_alternatives']
            or not all(isinstance(item, str) and item.strip() for item in document['rejected_alternatives'])):
        raise ValueError('Representation narrative evidence is missing')
    projected = deepcopy(document)
    projected.pop('transformation_rationale')
    projected.pop('rejected_alternatives')
    for member in projected['basket_members']:
        member.pop('selection_rationale')
    for transform in projected['transformations']:
        transform.pop('rationale')
    return projected


def representation_transition_evidence(
    accepted, released, *, accepted_digest, released_digest,
    release_source_commit, engineering_bundle_digest,
):
    """Preserve full hashes and expose narrative changes for separate review.

    Only explicitly enumerated narrative fields may differ. Matching projections
    do not establish scientific equivalence: prose can contain scientific claims.
    Callers must independently verify custody of the supplied source/bundle/inputs.
    """
    for value in (accepted_digest, released_digest, engineering_bundle_digest):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Transition evidence digest is invalid')
    if not isinstance(release_source_commit, str) or not re.fullmatch(r'[0-9a-f]{40}', release_source_commit):
        raise ValueError('Released source commit is invalid')
    accepted_projection, released_projection = _projection(accepted), _projection(released)
    if canonical_digest(accepted) != accepted_digest or canonical_digest(released) != released_digest:
        raise ValueError('Representation full-document digest mismatch')
    if canonical_digest(accepted_projection) != canonical_digest(released_projection):
        raise ValueError('Operational representation changed; separate design correction required')
    changes = []
    for key in ('transformation_rationale', 'rejected_alternatives'):
        if accepted[key] != released[key]:
            changes.append({'path': '/' + key, 'accepted': deepcopy(accepted[key]), 'released': deepcopy(released[key])})
    for collection, field in (('basket_members', 'selection_rationale'), ('transformations', 'rationale')):
        for index, (left, right) in enumerate(zip(accepted[collection], released[collection], strict=True)):
            if left[field] != right[field]:
                changes.append({'path': f'/{collection}/{index}/{field}',
                                'accepted': left[field], 'released': right[field]})
    evidence = dict(schema_version='released-representation-transition-v1',
        accepted_representation_digest=accepted_digest, released_representation_digest=released_digest,
        release_source_commit=release_source_commit, engineering_bundle_digest=engineering_bundle_digest,
        operational_projection_digest=canonical_digest(accepted_projection), narrative_changes=changes,
        disposition='requires_independent_execution_handoff_review',
        operational_projection_equal=True, scientific_equivalence_verified=False,
        execution_authority=False, historical_documents_mutated=False)
    return evidence | {'evidence_digest': canonical_digest(evidence)}
