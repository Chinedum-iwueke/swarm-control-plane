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
    'A generative law must specify innovation distributions, dimensions, scales and '
    'covariance, initialization/burn-in, transition coefficients, control columns, '
    'event thresholds and a single shared outcome equation. Distinguish assumed '
    'parameters from estimands induced by that law: correlated or nested events do '
    'not automatically yield the asserted conditional contrasts. Define every '
    'referenced symbol and coefficient, including how scenarios differ. '
    'Define a work unit and account for outer draws, scenarios, partitions, variants, '
    'statistics and sensitivity analyses; identify exactly which draws are shared '
    'and which estimator evaluations still cost work. State Monte Carlo precision '
    'and its acceptance criterion without claiming unexecuted calibration passed. '
    'Separate minimum eligible-row assumptions from native calendar capacity, '
    'warmup, split exclusions and target-only tail. A coverage-bound successor is '
    'authoritative only when explicitly included in the approved evidence; old '
    'dates remain historical evidence and must not be silently overwritten. '
    'Read current_authority alongside evidence: an active method-only lease binds '
    'the approved contract and dependencies; a retained draft flag saying approval '
    'was required does not undo that activation. It still grants no execution or '
    'scientific acceptance. Distinguish native diagnostic work-unit definitions '
    'from actual estimator compute costs. Do not silently replace one unit with '
    'another or reduce statistical precision just to fit a differently defined '
    'budget; expose both costs and any genuine capacity conflict for review. '
)
