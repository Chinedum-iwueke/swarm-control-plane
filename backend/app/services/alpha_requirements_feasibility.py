"""Bounded native planning task, reused by exact inputs before any paid review."""
from copy import deepcopy

from sqlalchemy import select

from app.models.task import Task
from app.schemas.task import TaskCreate
from app.services.graph import digest_document as digest
from app.services.tasks import build_task, persist_new_task


def planning_task(db, campaign, producer, evidence):
    contract = deepcopy(producer.input_contract)
    contract["feasibility_evidence"] = deepcopy(evidence)
    number = "AF-" + digest({"campaign": str(campaign.id), "parent": str(producer.id), "contract": contract})[:40]
    existing = db.scalar(select(Task).where(Task.task_number == number))
    if existing is not None:
        if existing.input_contract != contract or existing.parent_task_id != producer.id:
            raise ValueError("Native feasibility task identity conflict")
        return existing
    task = build_task(TaskCreate(
        task_number=number, project=producer.project, task_type="alpha_data_admission",
        title="Plan native smoke and scientific feasibility",
        objective="Check composed history and retained coverage before independent requirements review; no lake scan, model or execution.",
        parent_task_id=producer.id, created_by="alpha-requirements-director",
        risk_level=0, max_attempts=1, input_contract=contract,
        required_capabilities=list(producer.required_capabilities),
        allowed_machines=list(producer.allowed_machines),
        expected_outputs=["native requirements feasibility receipt"],
        acceptance_criteria=["Exact pinned source", "Separate smoke/scientific plans", "No capital authority"],
    ))
    persist_new_task(db, task)
    return task


def verified_report(task, evidence, source_commit):
    report = (task.result or {}).get("summary", {}).get("native_requirements_feasibility", {})
    if (
        report.get("schema_version") != "native-requirements-feasibility-v1"
        or report.get("source_commit") != source_commit
        or report.get("input_digest") != digest(evidence)
        or report.get("report_digest") != digest({k: v for k, v in report.items() if k != "report_digest"})
        or report.get("scientific_certification") is not False
        or report.get("execution_authority") is not False
        or report.get("status") not in {"ready", "deferred"}
        or not isinstance(report.get("reasons"), list)
    ):
        raise ValueError("Native feasibility receipt differs from immutable inputs")
    history = report.get("feature_history", {})
    outputs = history.get("outputs")
    if (not isinstance(outputs, dict) or not outputs
            or any(type(value) is not int or value < 0 for value in outputs.values())
            or history.get("minimum_prior_bars") != max(outputs.values())
            or history.get("declared_warmup_bars") != evidence["validation_requirements"]["requirements"]["feature_warmup_bars"]):
        raise ValueError("Native composed history receipt is incomplete")
    plans = report.get("validation_plans", {})
    if set(plans) != {"smoke", "scientific"}:
        raise ValueError("Separate smoke and scientific plans are required")
    for mode, plan in plans.items():
        if (plan.get("mode") != mode or plan.get("source_commit") != source_commit
                or plan.get("execution_authority") is not False
                or plan.get("plan_digest") != digest({k: v for k, v in plan.items() if k != "plan_digest"})):
            raise ValueError("Native validation plan custody differs")
    if report.get("status") == "ready" and (report.get("reasons") or any(p.get("status") != "ready" for p in plans.values()) or history["minimum_prior_bars"] > history["declared_warmup_bars"]):
        raise ValueError("Native readiness contradicts retained plans")
    return report


def reviewed_successor_inputs(report, evidence, mandate, source_commit):
    """Return proposed inputs for review, never execution or an in-place rewrite."""
    from app.services.alpha_coverage_successor import validate_native_proposal

    proposal = report.get("coverage_successor_proposal")
    if not isinstance(proposal, dict) or proposal.get("status") != "proposed":
        return None
    if (report["feature_history"]["minimum_prior_bars"] > report["feature_history"]["declared_warmup_bars"]
            or not report["reasons"]
            or any(reason not in {
                "smoke:insufficient_contiguous_eligible_basket_history",
                "scientific:insufficient_contiguous_eligible_basket_history",
            } for reason in report["reasons"])):
        raise ValueError("Only coverage failures can propose a pre-review successor")
    validate_native_proposal(evidence, report["validation_plans"]["scientific"], source_commit, mandate, proposal)
    parts = proposal["scientific_plan"]["partitions"]
    successor = deepcopy(evidence)
    successor["window"] = {"start": parts["feature_warmup"]["start"], "end": parts["target_tail"]["end"]}
    successor["validation_requirements"]["coverage"] = proposal["planning_inputs"]["coverage"]
    plans = report.get("successor_validation_plans") or {}
    if set(plans) != {"smoke", "scientific"}:
        raise ValueError("Successor requires both native validation plans")
    for mode, plan in plans.items():
        if (plan.get("status") != "ready" or plan.get("reasons") != []
                or plan.get("mode") != mode or plan.get("source_commit") != source_commit
                or plan.get("execution_authority") is not False
                or plan.get("plan_digest") != digest({k: v for k, v in plan.items() if k != "plan_digest"})):
            raise ValueError("Successor validation plan is not ready or digest-bound")
    if plans["scientific"]["partitions"] != parts:
        raise ValueError("Successor validation partitions differ from proposal")
    return successor
