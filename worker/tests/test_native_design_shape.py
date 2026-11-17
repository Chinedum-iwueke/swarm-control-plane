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
