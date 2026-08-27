from __future__ import annotations

import itertools
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.factor_language import FactorExperimentProgram
from app.models.research import ResearchHypothesis
from app.schemas.factor_language import FactorProgramCreate
from app.services.research import record_digest


class FactorLanguageConflict(RuntimeError):
    pass


_BINARY = {"add", "subtract", "multiply", "divide", "greater", "less", "and", "or"}
_UNARY = {"abs", "log", "negate"}


def _unit_for_binary(op: str, left: str, right: str) -> str:
    if op in {"add", "subtract", "greater", "less"} and left != right:
        raise FactorLanguageConflict(f"{op} operands must have identical units.")
    if op in {"and", "or"} and (left != "boolean" or right != "boolean"):
        raise FactorLanguageConflict(f"{op} operands must be boolean.")
    if op in {"greater", "less", "and", "or"}:
        return "boolean"
    if op in {"add", "subtract"}:
        return left
    if op == "multiply":
        if left == "dimensionless":
            return right
        if right == "dimensionless":
            return left
        return f"({left}*{right})"
    if right == left:
        return "dimensionless"
    if right == "dimensionless":
        return left
    return f"({left}/{right})"


def _compile_expression(
    node: Any,
    fields: dict,
    parameters: dict,
    path: str = "expression",
    depth: int = 0,
) -> tuple[dict, str]:
    if depth > 32:
        raise FactorLanguageConflict("Expression depth exceeds the language limit.")
    if not isinstance(node, dict) or set(node) != {"op", "args"}:
        raise FactorLanguageConflict(f"{path} must contain exactly op and args.")
    op, args = node["op"], node["args"]
    if not isinstance(args, list):
        raise FactorLanguageConflict(f"{path}.args must be a list.")
    if op == "field":
        if len(args) != 2 or args[0] not in fields or not isinstance(args[1], int):
            raise FactorLanguageConflict(
                f"{path} field requires [known_field, positive_lag]."
            )
        field, lag = args
        effective_lag = lag + fields[field]["availability_lag"]
        if lag < 0 or effective_lag < 1:
            raise FactorLanguageConflict(
                f"{path} reads {field} before it is causally available."
            )
        return {"op": op, "field": field, "effective_lag": effective_lag}, fields[
            field
        ]["unit"]
    if op == "constant":
        if (
            len(args) != 1
            or isinstance(args[0], bool)
            or not isinstance(args[0], (int, float))
            or not math.isfinite(args[0])
        ):
            raise FactorLanguageConflict(f"{path} constant must be one finite number.")
        return {"op": op, "value": args[0]}, "dimensionless"
    if op == "parameter":
        if len(args) != 1 or args[0] not in parameters:
            raise FactorLanguageConflict(f"{path} references an undeclared parameter.")
        return {"op": op, "name": args[0]}, "dimensionless"
    if op == "lag":
        if len(args) != 2 or not isinstance(args[1], int) or args[1] < 1:
            raise FactorLanguageConflict(
                f"{path} lag requires [expression, positive_integer]."
            )
        child, unit = _compile_expression(
            args[0], fields, parameters, f"{path}.args[0]", depth + 1
        )
        return {"op": op, "args": [child, args[1]]}, unit
    if op == "rolling_mean":
        if len(args) != 2:
            raise FactorLanguageConflict(
                f"{path} rolling_mean requires [expression, window]."
            )
        child, unit = _compile_expression(
            args[0], fields, parameters, f"{path}.args[0]", depth + 1
        )
        window = args[1]
        valid = (isinstance(window, int) and window >= 2) or (
            isinstance(window, dict) and window.get("op") == "parameter"
        )
        if not valid:
            raise FactorLanguageConflict(
                f"{path} rolling window must be >=2 or a parameter."
            )
        compiled_window = (
            _compile_expression(
                window, fields, parameters, f"{path}.args[1]", depth + 1
            )[0]
            if isinstance(window, dict)
            else window
        )
        return {"op": op, "args": [child, compiled_window]}, unit
    if op in _UNARY:
        if len(args) != 1:
            raise FactorLanguageConflict(f"{path} {op} requires one argument.")
        child, unit = _compile_expression(
            args[0], fields, parameters, f"{path}.args[0]", depth + 1
        )
        if op == "log" and unit != "dimensionless":
            raise FactorLanguageConflict("log requires a dimensionless expression.")
        return {"op": op, "args": [child]}, unit
    if op in _BINARY:
        if len(args) != 2:
            raise FactorLanguageConflict(f"{path} {op} requires two arguments.")
        left, left_unit = _compile_expression(
            args[0], fields, parameters, f"{path}.args[0]", depth + 1
        )
        right, right_unit = _compile_expression(
            args[1], fields, parameters, f"{path}.args[1]", depth + 1
        )
        return {"op": op, "args": [left, right]}, _unit_for_binary(
            op, left_unit, right_unit
        )
    raise FactorLanguageConflict(f"{path} uses unsupported operator {op!r}.")


def compile_program(payload: FactorProgramCreate) -> tuple[dict, str, str, str]:
    source = payload.source.model_dump(mode="json")
    fields = {
        key: value.model_dump(mode="json")
        for key, value in payload.source.fields.items()
    }
    parameters = source["parameters"]
    for name, values in parameters.items():
        if not values or len(values) != len({record_digest(value) for value in values}):
            raise FactorLanguageConflict(
                f"Parameter {name} must contain distinct values."
            )
        if any(
            isinstance(value, float) and not math.isfinite(value) for value in values
        ):
            raise FactorLanguageConflict(
                f"Parameter {name} contains a non-finite value."
            )
    combinations = (
        math.prod(len(values) for values in parameters.values()) if parameters else 1
    )
    if combinations > payload.source.maximum_trials:
        raise FactorLanguageConflict("Parameter grid exceeds maximum_trials.")
    compiled_factors = {}
    for name, factor in sorted(payload.source.factors.items()):
        expression, inferred_unit = _compile_expression(
            factor.expression, fields, parameters, f"factors.{name}"
        )
        if inferred_unit != factor.output_unit:
            raise FactorLanguageConflict(
                f"Factor {name} declares {factor.output_unit}, inferred {inferred_unit}."
            )
        compiled_factors[name] = {
            "expression": expression,
            "unit": inferred_unit,
            "missing_policy": factor.missing_policy,
        }
    if payload.source.label.field not in fields:
        raise FactorLanguageConflict("Label references an unknown field.")
    names = sorted(parameters)
    variants = []
    for values in (
        itertools.product(*(parameters[name] for name in names)) if names else [()]
    ):
        assignment = dict(zip(names, values, strict=True))
        variant = {"ordinal": len(variants) + 1, "parameters": assignment}
        variant["trial_digest"] = record_digest(
            {"source": source, "parameters": assignment}
        )
        variants.append(variant)
    semantic = {
        "language_version": source["schema_version"],
        "hypothesis_id": str(payload.hypothesis_id),
        "source": source,
    }
    compiled = {
        "schema_version": "factor-experiment-ir-v1.0.0",
        "source_digest": record_digest(source),
        "representation_contract_digest": source["representation_contract_digest"],
        "dataset_manifest_digest": source["dataset_manifest_digest"],
        "factors": compiled_factors,
        "label": source["label"],
        "trial_count": len(variants),
        "trials": variants,
        "action_authority": False,
    }
    return (
        compiled,
        record_digest(source),
        record_digest(semantic),
        record_digest(compiled),
    )


def register_factor_program(
    db: Session, payload: FactorProgramCreate
) -> FactorExperimentProgram:
    if db.get(ResearchHypothesis, payload.hypothesis_id) is None:
        raise FactorLanguageConflict("A registered hypothesis is required.")
    compiled, source_digest, semantic_digest, compiled_digest = compile_program(payload)
    prior = None
    if payload.supersedes_program_id:
        prior = db.scalar(
            select(FactorExperimentProgram)
            .where(FactorExperimentProgram.id == payload.supersedes_program_id)
            .with_for_update()
        )
        if (
            prior is None
            or prior.status != "active"
            or prior.hypothesis_id != payload.hypothesis_id
        ):
            raise FactorLanguageConflict(
                "Superseded program is absent, inactive, or belongs to another hypothesis."
            )
        prior.status = "superseded"
    record = FactorExperimentProgram(
        program_key=payload.program_key,
        hypothesis_id=payload.hypothesis_id,
        language_version=payload.source.schema_version,
        source=payload.source.model_dump(mode="json"),
        source_digest=source_digest,
        semantic_digest=semantic_digest,
        compiled=compiled,
        compiled_digest=compiled_digest,
        supersedes_program_id=payload.supersedes_program_id,
        registered_by=payload.registered_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise FactorLanguageConflict(
            "Program key, source, semantics, or compiled artifact already exists."
        ) from exc
    return record
