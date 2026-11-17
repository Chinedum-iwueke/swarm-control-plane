"""Strict author-output shape; native tools own semantic consistency checks."""


def design_schema():
    def obj(properties):
        return {'type': 'object', 'additionalProperties': False,
                'required': list(properties), 'properties': properties}

    text = {'type': 'string'}
    strings = {'type': 'array', 'items': text}
    family = obj({'id': text, 'variant_ids': strings})
    optional_number = {'anyOf': [{'type': 'number'}, {'type': 'null'}]}
    cell = obj({'partition_id': text, 'variant_id': text,
                'event_probability': optional_number, 'expected_events': optional_number,
                'sampling_rule': text})
    scenario = obj({'id': text, 'families': {'type': 'array', 'items': family},
        'cells': {'type': 'array', 'items': cell}, 'joint_generation': text,
        'null_or_effect': text, 'estimator_application': text, 'seed_schedule': text,
        'outputs': text, 'event_rate_mode': {'type': 'string', 'enum': ['registered', 'sensitivity']},
        'event_rate_assumption': text})
    return obj({'purpose': {'type': 'string', 'enum': ['scientific', 'diagnostic']},
                'statistic_id': text, 'scenarios': {'type': 'array', 'items': scenario}})


CORRECTION_GUIDANCE = (
    'Treat method.experiment, when present, as the immutable experiment definition. '
    'Construct calibration_design for its exact variants, families, partitions and procedure, '
    'not a convenient single-variant substitute. Define joint generation across all family '
    'members, including event generation, dependence, null/effect parameterization, estimator '
    'application, seeds and outputs. Expected event counts are assumptions (rows times '
    'probability), not realized support or guaranteed power; make conditioning explicit. '
    'Keep replicate counts consistent with the registered purpose; do not relabel a cheaper '
    'diagnostic as scientific calibration. Explain assumptions requiring independent review. '
    'Use the native findings to repair the design within the allowed fields and budget; '
    'never change the frozen experiment or invent observed results. Labels and prose cannot '
    'prove executable DGP parity. If the frozen contract is inconsistent, retain that blocker '
    'rather than silently repairing authority. '
)
