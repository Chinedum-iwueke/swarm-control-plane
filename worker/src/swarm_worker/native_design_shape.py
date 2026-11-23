"""Cheap wire-shape checks, not scientific validity or a native receipt."""
import math
import re

FIELDS = {'schema_version', 'estimand', 'estimator_id', 'meaningful_effect',
          'dependence_assumptions', 'multiplicity', 'eligibility_policy',
          'undefined_replicate_policy', 'calibration'}
SHAPE = {
    'meaningful_effect': {'value': 'finite positive number, not boolean',
        'units': 'nonempty string, at most 4000 characters',
        'justification': 'nonempty string, at most 4000 characters',
        'evidence_digests': '1..16 SHA-256 digests of retained evidence'},
    'calibration': {'seed': 'integer 0..4294967295',
        'outer_replicates': 'integer 1..10000', 'inner_replicates': 'integer 1..10000',
        'max_work_units': 'prospective integer 1..1000000000000000; not execution authority',
        'dgp_ids': '1..16 unique identifiers matching [a-z0-9_-]{1,80}'},
    'work_rule': 'len(dgp_ids) * outer_replicates * inner_replicates <= max_work_units',
    'statements': 'Other method fields except schema_version are nonempty strings <=4000 characters',
    'authority': 'Shape validity is not scientific approval; native diagnosis and independent review remain required',
}


def defects(method):
    errors = {field: 'Native design requires ' + field for field in sorted(FIELDS - method.keys())}
    for field in FIELDS - {'schema_version', 'meaningful_effect', 'calibration'}:
        if field in method and (not isinstance(method[field], str) or not 1 <= len(method[field].strip()) <= 4000):
            errors[field] = 'Required nonempty statement of at most 4000 characters'
    effect = method.get('meaningful_effect')
    if effect is not None:
        valid = isinstance(effect, dict) and set(effect) == set(SHAPE['meaningful_effect'])
        if valid:
            value, refs = effect['value'], effect['evidence_digests']
            valid = (type(value) in (int, float) and math.isfinite(value) and value > 0
                and all(isinstance(effect[k], str) and 1 <= len(effect[k].strip()) <= 4000 for k in ('units', 'justification'))
                and isinstance(refs, list) and 1 <= len(refs) <= 16
                and all(isinstance(v, str) and re.fullmatch('[a-f0-9]{64}', v) for v in refs))
        if not valid:
            errors['meaningful_effect'] = 'Use exactly the required meaningful_effect object shape; no renamed or extra fields'
    calibration = method.get('calibration')
    if calibration is not None:
        valid = isinstance(calibration, dict) and set(calibration) == set(SHAPE['calibration'])
        if valid:
            valid = all(type(calibration[k]) is int and lo <= calibration[k] <= hi for k, lo, hi in (
                ('seed', 0, 2**32-1), ('outer_replicates', 1, 10000),
                ('inner_replicates', 1, 10000), ('max_work_units', 1, 10**15)))
            dgps = calibration['dgp_ids']
            valid = (valid and isinstance(dgps, list) and 1 <= len(dgps) <= 16
                and all(isinstance(v, str) and re.fullmatch('[a-z0-9_-]{1,80}', v) for v in dgps))
            if valid:
                valid = len(dgps) == len(set(dgps)) and len(dgps)*calibration['outer_replicates']*calibration['inner_replicates'] <= calibration['max_work_units']
        if not valid:
            errors['calibration'] = 'Use the exact bounded calibration shape and satisfy its declared work rule'
    for field in ('meaningful_effect', 'calibration'):
        if field in method and method[field] is None:
            errors[field] = 'Null is not a valid native design object'
    return errors
