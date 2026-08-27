from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.discovery import DiscoveryMap
from app.models.evidence import CanonicalEvidenceObject
from app.models.falsification import MechanismEvaluation, MechanismPlan
from app.models.memory import EvidenceDossier, EvidenceOppositionRecord
from app.models.research import ResearchHypothesis
from app.schemas.falsification import MechanismEvaluationCreate, MechanismPlanCreate
from app.services.research import record_digest


class FalsificationConflict(RuntimeError):
    pass


def register_plan(db: Session, payload: MechanismPlanCreate) -> MechanismPlan:
    if record_digest(payload.plan) != payload.plan_digest:
        raise FalsificationConflict("Plan digest does not match canonical content.")
    mapped = db.get(DiscoveryMap, payload.discovery_map_id)
    if (
        mapped is None
        or mapped.status != "active"
        or mapped.stage not in {"mechanism", "opportunity"}
    ):
        raise FalsificationConflict("Active mechanism or opportunity map is required.")
    if db.get(ResearchHypothesis, payload.hypothesis_id) is None:
        raise FalsificationConflict("Registered hypothesis is required.")
    dossiers = list(
        db.scalars(
            select(EvidenceDossier).where(
                EvidenceDossier.id.in_(payload.plan.dossier_ids)
            )
        ).all()
    )
    opposition = list(
        db.scalars(
            select(EvidenceOppositionRecord).where(
                EvidenceOppositionRecord.id.in_(payload.plan.opposition_record_ids)
            )
        ).all()
    )
    if len(dossiers) != len(payload.plan.dossier_ids) or len(opposition) != len(
        payload.plan.opposition_record_ids
    ):
        raise FalsificationConflict("Dossier or opposition provenance is incomplete.")
    record = MechanismPlan(
        plan_key=payload.plan_key,
        discovery_map_id=payload.discovery_map_id,
        hypothesis_id=payload.hypothesis_id,
        plan=payload.plan.model_dump(mode="json"),
        plan_digest=payload.plan_digest,
        registered_by=payload.registered_by,
    )
    db.add(record)
    db.flush()
    return record


def register_evaluation(
    db: Session, payload: MechanismEvaluationCreate
) -> MechanismEvaluation:
    if record_digest(payload.evaluation) != payload.evaluation_digest:
        raise FalsificationConflict(
            "Evaluation digest does not match canonical content."
        )
    plan = db.scalar(
        select(MechanismPlan)
        .where(MechanismPlan.id == payload.plan_id)
        .with_for_update()
    )
    if plan is None or plan.plan_digest != payload.evaluation.plan_digest:
        raise FalsificationConflict("Evaluation does not bind the registered plan.")
    if payload.evaluation.evaluated_at <= plan.registered_at:
        raise FalsificationConflict(
            "Decisive outcomes must postdate plan registration."
        )
    planned = {item["test_key"]: item for item in plan.plan["decisive_tests"]}
    outcomes = {item.test_key: item for item in payload.evaluation.outcomes}
    if set(outcomes) != set(planned):
        raise FalsificationConflict(
            "Every preregistered decisive test requires exactly one outcome."
        )
    evidence = list(
        db.scalars(
            select(CanonicalEvidenceObject).where(
                CanonicalEvidenceObject.id.in_(
                    [item.evidence_object_id for item in outcomes.values()]
                )
            )
        ).all()
    )
    if len(evidence) != len(outcomes) or {item.content_digest for item in evidence} != {
        item.evidence_digest for item in outcomes.values()
    }:
        raise FalsificationConflict(
            "Outcome evidence identities and digests do not match."
        )
    for key, outcome in outcomes.items():
        expected = set(planned[key]["target_alternatives"])
        if set(outcome.rival_outcomes) != expected:
            raise FalsificationConflict(
                "Rival outcomes must cover the preregistered alternatives."
            )
    if any(item.outcome == "failed" for item in outcomes.values()):
        conclusion = "falsified"
    elif all(item.outcome == "passed" for item in outcomes.values()) and all(
        result == "ruled_out"
        for item in outcomes.values()
        for result in item.rival_outcomes.values()
    ):
        conclusion = "supported"
    else:
        conclusion = "unresolved"
    prior = None
    if payload.supersedes_evaluation_id:
        prior = db.scalar(
            select(MechanismEvaluation)
            .where(MechanismEvaluation.id == payload.supersedes_evaluation_id)
            .with_for_update()
        )
        if prior is None or prior.status != "active" or prior.plan_id != plan.id:
            raise FalsificationConflict(
                "Superseded evaluation is absent, inactive or belongs to another plan."
            )
        prior.status = "superseded"
    record = MechanismEvaluation(
        evaluation_key=payload.evaluation_key,
        plan_id=plan.id,
        evaluation=payload.evaluation.model_dump(mode="json"),
        conclusion=conclusion,
        evaluation_digest=payload.evaluation_digest,
        supersedes_evaluation_id=payload.supersedes_evaluation_id,
        status="active",
        evaluated_by=payload.evaluated_by,
        evaluated_at=payload.evaluation.evaluated_at,
    )
    db.add(record)
    db.flush()
    return record
