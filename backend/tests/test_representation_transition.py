from copy import deepcopy

import pytest

from app.contracts.representation_transition import representation_transition_evidence
from app.schemas.method_task import canonical_digest as digest


def plan():
    return dict(schema_version='adaptive-representation-plan-v1.0.0', candidate_key='example',
        instruments=['ETHUSDT'], basket_members=[dict(instrument='ETHUSDT', role='primary',
            legacy_groups=['volatile'], selection_rationale='One independently selected instrument.')],
        source_timeframe='1m', research_timeframe='15m',
        resampling_policy='left_closed_left_labeled_complete_bars',
        transformations=[dict(operation='log_return', input_fields=['ETHUSDT__close'],
            output_field='return_15m', parameters={'periods':1}, fit_policy='stateless',
            rationale='Completed causal return with no fitted state.')],
        transformation_rationale='Use only completed returns for this experiment.',
        rejected_alternatives=['Future values are not eligible predictors.'],
        selection_data_boundary='metadata_predictors_only_no_targets', outcome_data_consulted=False)


def compare(a, b, **kwargs):
    return representation_transition_evidence(a, b, **(dict(accepted_digest=digest(a),
        released_digest=digest(b), release_source_commit='a'*40, engineering_bundle_digest='b'*64) | kwargs))


def test_narrative_changes_are_lossless_non_authoritative_and_idempotent():
    a = plan()
    b = deepcopy(a)
    b['transformations'][0]['rationale'] = 'Same completed return; execution reviewer must inspect this explanation.'
    before = deepcopy((a,b))
    evidence = compare(a,b)
    assert evidence == compare(a,b)
    assert (a,b) == before
    assert evidence['accepted_representation_digest'] != evidence['released_representation_digest']
    assert evidence['narrative_changes'] == [dict(path='/transformations/0/rationale',
        accepted=a['transformations'][0]['rationale'], released=b['transformations'][0]['rationale'])]
    assert not evidence['execution_authority']
    assert not evidence['scientific_equivalence_verified']
    assert evidence['evidence_digest'] == digest({k:v for k,v in evidence.items() if k != 'evidence_digest'})


def test_identical_documents_still_do_not_grant_authority():
    evidence = compare(plan(), plan())
    assert evidence['narrative_changes'] == []
    assert evidence['disposition'] == 'requires_independent_execution_handoff_review'


@pytest.mark.parametrize('field,value', [('research_timeframe','30m'), ('candidate_key','other')])
def test_clock_or_identity_changes_require_design_correction(field, value):
    a = plan(); b = deepcopy(a); b[field] = value
    with pytest.raises(ValueError, match='Operational'):
        compare(a,b)


@pytest.mark.parametrize('field,value', [('parameters',{'periods':2}),
    ('input_fields',['ETHUSDT__open']), ('output_field','different_return'), ('operation','simple_return')])
def test_operator_changes_cannot_be_hidden_as_documentation(field, value):
    a = plan(); b = deepcopy(a); b['transformations'][0][field] = value
    with pytest.raises(ValueError, match='Operational'):
        compare(a,b)


@pytest.mark.parametrize('field', ['accepted_digest','released_digest'])
def test_full_document_hash_remains_mandatory(field):
    with pytest.raises(ValueError, match='full-document'):
        compare(plan(),plan(),**{field:'f'*64})


def test_new_fields_and_unsafe_selection_fail_closed():
    a = plan(); b = deepcopy(a); b['unreviewed_option'] = True
    with pytest.raises(ValueError, match='exact'):
        compare(a,b)
    b = deepcopy(a); b['outcome_data_consulted'] = True
    with pytest.raises(ValueError, match='unsafe'):
        compare(a,b)


def test_basket_and_duplicate_outputs_remain_identity_bearing():
    a = plan(); b = deepcopy(a); b['basket_members'][0]['legacy_groups'] = ['stable']
    with pytest.raises(ValueError, match='Operational'):
        compare(a,b)
    b = deepcopy(a); b['transformations'].append(deepcopy(b['transformations'][0]))
    with pytest.raises(ValueError, match='ambiguous'):
        compare(a,b)


def test_unknown_operator_fields_are_not_discarded():
    a = plan(); b = deepcopy(a); b['transformations'][0]['hidden_lag'] = -1
    with pytest.raises(ValueError):
        compare(a,b)
