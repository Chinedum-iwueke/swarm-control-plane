from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.factor_language import FactorExperimentProgram
from app.models.prompt_policy import PromptPolicyBundle
from app.models.symbolic_search import SymbolicSearchCandidate, SymbolicSearchRun
from app.schemas.symbolic_search import SymbolicCandidateCreate, SymbolicSearchCreate
from app.services.factor_language import FactorLanguageConflict, _compile_expression
from app.services.research import record_digest


class SymbolicSearchConflict(RuntimeError):
    pass


_COMMUTATIVE = {"add", "multiply", "and", "or"}
_SAFE_GENERATOR_TOOLS = {"research.retrieve"}


def _walk(node: Any, depth: int = 1) -> tuple[int, int, int, set[str], set[str]]:
    if (
        not isinstance(node, dict)
        or set(node) != {"op", "args"}
        or not isinstance(node["args"], list)
    ):
        raise SymbolicSearchConflict(
            "Expression nodes must contain exactly op and list args."
        )
    nodes, maximum_depth, constants = 1, depth, 0
    operators, fields = {str(node["op"])}, set()
    if node["op"] == "constant":
        constants += 1
    if node["op"] == "field" and node["args"] and isinstance(node["args"][0], str):
        fields.add(node["args"][0])
    for child in node["args"]:
        if isinstance(child, dict):
            child_nodes, child_depth, child_constants, child_ops, child_fields = _walk(
                child, depth + 1
            )
            nodes += child_nodes
            maximum_depth = max(maximum_depth, child_depth)
            constants += child_constants
            operators.update(child_ops)
            fields.update(child_fields)
    return nodes, maximum_depth, constants, operators, fields


def _normalize(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    normalized = {
        "op": node.get("op"),
        "args": [_normalize(item) for item in node.get("args", [])],
    }
    if normalized["op"] in _COMMUTATIVE:
        normalized["args"] = sorted(normalized["args"], key=record_digest)
    return normalized


def register_symbolic_search(
    db: Session, payload: SymbolicSearchCreate
) -> SymbolicSearchRun:
    program = db.get(FactorExperimentProgram, payload.base_factor_program_id)
    if program is None or program.status != "active":
        raise SymbolicSearchConflict("An active DISC-003 factor program is required.")
    policy = db.get(PromptPolicyBundle, payload.prompt_policy_bundle_id)
    if policy is None or policy.status != "active":
        raise SymbolicSearchConflict("An active AGT-004 prompt policy is required.")
    unsafe_tools = set(policy.allowed_tools) - _SAFE_GENERATOR_TOOLS
    if policy.policy.get("output_authority") != "data_only" or unsafe_tools:
        raise SymbolicSearchConflict(
            "Generator policy must be data-only and contains unsafe tools: "
            f"{sorted(unsafe_tools)}"
        )
    unknown = set(payload.constraints.required_fields) - set(program.source["fields"])
    if unknown:
        raise SymbolicSearchConflict(
            f"Required fields are absent from the base program: {sorted(unknown)}"
        )
    constraints = payload.constraints.model_dump(mode="json")
    constraints.update(
        {
            "base_factor_program_digest": program.compiled_digest,
            "prompt_policy_digest": policy.bundle_digest,
        }
    )
    constraints_digest = record_digest(constraints)
    existing = db.scalar(
        select(SymbolicSearchRun).where(
            (SymbolicSearchRun.run_key == payload.run_key)
            | (SymbolicSearchRun.constraints_digest == constraints_digest)
        )
    )
    if existing is not None:
        if existing.constraints_digest == constraints_digest:
            return existing
        raise SymbolicSearchConflict("Run key already has different constraints.")
    record = SymbolicSearchRun(
        run_key=payload.run_key,
        base_factor_program_id=program.id,
        prompt_policy_bundle_id=policy.id,
        constraints=constraints,
        constraints_digest=constraints_digest,
        generated_by=payload.generated_by,
    )
    db.add(record)
    db.flush()
    return record


def validate_candidate(
    db: Session, run_id, payload: SymbolicCandidateCreate
) -> SymbolicSearchCandidate:
    run = db.scalar(
        select(SymbolicSearchRun)
        .where(SymbolicSearchRun.id == run_id)
        .with_for_update()
    )
    if run is None or run.status != "active":
        raise SymbolicSearchConflict("An active symbolic-search run is required.")
    prior = list(
        db.scalars(
            select(SymbolicSearchCandidate)
            .where(SymbolicSearchCandidate.run_id == run.id)
            .order_by(SymbolicSearchCandidate.created_at)
        ).all()
    )
    proposal = {
        "expression": payload.expression,
        "output_unit": payload.output_unit,
        "generator": payload.generator.model_dump(mode="json"),
    }
    actual_output_digest = record_digest(proposal)
    proposal_digest = record_digest(
        {
            "run_constraints_digest": run.constraints_digest,
            "proposal": proposal,
            "claimed_output_digest": payload.output_digest,
        }
    )
    existing = next(
        (item for item in prior if item.proposal_digest == proposal_digest), None
    )
    if existing is not None:
        return existing
    if any(item.candidate_key == payload.candidate_key for item in prior):
        raise SymbolicSearchConflict("Candidate key already has different content.")
    if len(prior) >= run.constraints["maximum_candidates"]:
        run.status = "complete"
        raise SymbolicSearchConflict("Symbolic-search candidate budget is exhausted.")
    violations = []
    same_generation = [
        item
        for item in prior
        if item.proposal.get("generator") == proposal["generator"]
    ]
    if same_generation and any(
        item.proposal.get("expression") != proposal["expression"]
        or item.proposal.get("output_unit") != proposal["output_unit"]
        for item in same_generation
    ):
        violations.append("nondeterministic_generator_output")
    semantic_digest = None
    compiled = {}
    try:
        nodes, depth, constants, operators, fields = _walk(payload.expression)
        if actual_output_digest != payload.output_digest:
            violations.append("generator_output_digest_mismatch")
        disallowed = operators - set(run.constraints["allowed_operators"])
        if disallowed:
            violations.append(f"disallowed_operators:{','.join(sorted(disallowed))}")
        if not run.constraints["allow_parameters"] and "parameter" in operators:
            violations.append("parameters_forbidden")
        if nodes > run.constraints["maximum_nodes"]:
            violations.append("maximum_nodes_exceeded")
        if depth > run.constraints["maximum_depth"]:
            violations.append("maximum_depth_exceeded")
        if constants > run.constraints["maximum_constants"]:
            violations.append("maximum_constants_exceeded")
        missing = set(run.constraints["required_fields"]) - fields
        if missing:
            violations.append(f"required_fields_missing:{','.join(sorted(missing))}")
        program = db.get(FactorExperimentProgram, run.base_factor_program_id)
        fields_contract = program.source["fields"]
        parameters = (
            program.source["parameters"] if run.constraints["allow_parameters"] else {}
        )
        if not violations:
            compiled_expression, inferred_unit = _compile_expression(
                payload.expression, fields_contract, parameters
            )
            if inferred_unit != payload.output_unit:
                violations.append(f"unit_mismatch:{inferred_unit}")
            else:
                normalized = _normalize(payload.expression)
                semantic_digest = record_digest(
                    {"expression": normalized, "output_unit": inferred_unit}
                )
                base_digests = {
                    record_digest(
                        {
                            "expression": _normalize(factor["expression"]),
                            "output_unit": factor["output_unit"],
                        }
                    )
                    for factor in program.source["factors"].values()
                }
                accepted_digests = {
                    item.semantic_digest for item in prior if item.status == "accepted"
                }
                if (
                    semantic_digest in base_digests
                    or semantic_digest in accepted_digests
                ):
                    violations.append("semantic_duplicate")
                else:
                    compiled = {
                        "expression": compiled_expression,
                        "unit": inferred_unit,
                        "nodes": nodes,
                        "depth": depth,
                        "constants": constants,
                        "action_authority": False,
                    }
    except (SymbolicSearchConflict, FactorLanguageConflict) as exc:
        violations.append(f"compiler_rejection:{exc}")
    status = (
        "duplicate"
        if "semantic_duplicate" in violations
        else "rejected"
        if violations
        else "accepted"
    )
    validation = {
        "proposal_digest": proposal_digest,
        "semantic_digest": semantic_digest,
        "status": status,
        "violations": violations,
        "compiled": compiled,
        "constraints_digest": run.constraints_digest,
    }
    record = SymbolicSearchCandidate(
        run_id=run.id,
        candidate_key=payload.candidate_key,
        proposal=proposal,
        proposal_digest=proposal_digest,
        semantic_digest=semantic_digest,
        status=status,
        violations=violations,
        compiled=compiled,
        validation_digest=record_digest(validation),
        submitted_by=payload.submitted_by,
    )
    db.add(record)
    db.flush()
    run.candidate_count += 1
    if status == "accepted":
        run.accepted_count += 1
    if run.candidate_count == run.constraints["maximum_candidates"]:
        run.status = "complete"
    return record


def quarantine_run(db: Session, run_id, actor: str, reason: str) -> SymbolicSearchRun:
    run = db.scalar(
        select(SymbolicSearchRun)
        .where(SymbolicSearchRun.id == run_id)
        .with_for_update()
    )
    if run is None or run.status != "active":
        raise SymbolicSearchConflict("An active symbolic-search run is required.")
    run.status = "quarantined"
    run.closure = {
        "actor": actor,
        "reason": reason,
        "candidate_count": run.candidate_count,
        "accepted_count": run.accepted_count,
        "lineage_retained": True,
        "action_authority": False,
    }
    return run
