from copy import deepcopy
import pytest
from pydantic import ValidationError
from swarm_worker.models import WorkflowExecutionResult
from swarm_worker.native_design_shape import defects
from test_alpha_method_design import contract


@pytest.mark.parametrize('field,value', [
    ('meaningful_effect', {'standardized_value': .2}),
    ('meaningful_effect', None),
    ('calibration', {'seed': 1}),
    ('undefined_replicate_policy', {}),
])
def test_malformed_native_fields_are_actionable_before_native_execution(field, value):
    method = deepcopy(contract('a'*40)['proposal']['method'])
    assert not defects(method)
    method[field] = value
    assert field in defects(method)


def test_method_results_have_bounded_evidence_capacity_without_relaxing_other_workflows():
    common = dict(repository='bulletproof_bt', base_commit='a'*40, task_attempt=1,
                  total_duration_seconds=1, steps=[], success=True)
    WorkflowExecutionResult(workflow='alpha-method-design', summary={'evidence': 'x'*200000}, **common)
    with pytest.raises(ValidationError, match='256 KiB'):
        WorkflowExecutionResult(workflow='alpha-method-design', summary={'evidence': 'x'*262144}, **common)
    with pytest.raises(ValidationError, match='16 KiB'):
        WorkflowExecutionResult(workflow='engineering-mission', summary={'evidence': 'x'*20000}, **common)


@pytest.mark.parametrize('budget,valid', [(266240000, True), (10**15, True),
                                        (10**15 + 1, False), (True, False)])
def test_prospective_budget_has_distinct_bounds_and_matching_api_shape(budget, valid):
    import runpy
    from pathlib import Path
    api = runpy.run_path(str(Path(__file__).resolve().parents[2]
                            / 'backend/app/contracts/native_design_shape.py'))
    method = deepcopy(contract('a'*40)['proposal']['method'])
    method['calibration']['max_work_units'] = budget
    assert ('calibration' not in defects(method)) is valid
    assert api['defects'](method) == defects(method)


def test_execution_reservation_is_not_a_prospective_design_budget():
    from swarm_worker.method_episode import MethodEpisodePolicy
    with pytest.raises(ValidationError, match='max_work_units'):
        MethodEpisodePolicy(max_work_units=266240000, allowed_method_fields=['calibration'])
