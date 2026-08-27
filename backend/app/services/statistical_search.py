from __future__ import annotations

import hashlib
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.factor_language import FactorExperimentProgram
from app.models.statistical_search import (
    StatisticalSearchCampaign,
    StatisticalSearchEvent,
)
from app.schemas.statistical_search import (
    SearchObservationBatch,
    StatisticalSearchCreate,
)
from app.services.research import record_digest

ZERO_DIGEST = "0" * 64


class StatisticalSearchConflict(RuntimeError):
    pass


def _events(db: Session, campaign_id) -> list[StatisticalSearchEvent]:
    return list(
        db.scalars(
            select(StatisticalSearchEvent)
            .where(StatisticalSearchEvent.campaign_id == campaign_id)
            .order_by(StatisticalSearchEvent.sequence)
        ).all()
    )


def verify_event_chain(
    campaign: StatisticalSearchCampaign, events: list[StatisticalSearchEvent]
) -> bool:
    prior = ZERO_DIGEST
    for sequence, event in enumerate(events, start=1):
        document = {
            "campaign_id": str(campaign.id),
            "sequence": sequence,
            "event_type": event.event_type,
            "detail": event.detail,
            "prior_digest": prior,
        }
        if (
            event.sequence != sequence
            or event.prior_digest != prior
            or event.record_digest != record_digest(document)
        ):
            return False
        prior = event.record_digest
    return prior == campaign.event_head_digest


def _append(
    db: Session, campaign: StatisticalSearchCampaign, event_type: str, detail: dict
) -> StatisticalSearchEvent:
    sequence = len(_events(db, campaign.id)) + 1
    document = {
        "campaign_id": str(campaign.id),
        "sequence": sequence,
        "event_type": event_type,
        "detail": detail,
        "prior_digest": campaign.event_head_digest,
    }
    event = StatisticalSearchEvent(
        campaign_id=campaign.id,
        sequence=sequence,
        event_type=event_type,
        detail=detail,
        prior_digest=campaign.event_head_digest,
        record_digest=record_digest(document),
    )
    db.add(event)
    db.flush()
    campaign.event_head_digest = event.record_digest
    return event


def register_campaign(
    db: Session, payload: StatisticalSearchCreate
) -> StatisticalSearchCampaign:
    program = db.get(FactorExperimentProgram, payload.factor_program_id)
    if program is None or program.status != "active":
        raise StatisticalSearchConflict("An active factor program is required.")
    trials = program.compiled["trials"]
    if payload.budget.maximum_evaluations > len(trials):
        raise StatisticalSearchConflict(
            "Evaluation budget exceeds the compiled trial universe."
        )
    if payload.method == "exhaustive" and payload.budget.maximum_evaluations != len(
        trials
    ):
        raise StatisticalSearchConflict(
            "Exhaustive search must budget the complete universe."
        )
    specification = payload.model_dump(
        mode="json", exclude={"campaign_key", "registered_by"}
    )
    specification["factor_program_digest"] = program.compiled_digest
    specification_digest = record_digest(specification)
    existing = db.scalar(
        select(StatisticalSearchCampaign).where(
            (StatisticalSearchCampaign.campaign_key == payload.campaign_key)
            | (StatisticalSearchCampaign.specification_digest == specification_digest)
        )
    )
    if existing is not None:
        if existing.specification_digest == specification_digest:
            return existing
        raise StatisticalSearchConflict("Campaign key already has different semantics.")
    campaign = StatisticalSearchCampaign(
        campaign_key=payload.campaign_key,
        factor_program_id=program.id,
        method=payload.method,
        specification=specification,
        specification_digest=specification_digest,
        event_head_digest=ZERO_DIGEST,
        registered_by=payload.registered_by,
    )
    db.add(campaign)
    db.flush()
    _append(
        db,
        campaign,
        "registered",
        {
            "specification_digest": campaign.specification_digest,
            "trial_universe_digest": record_digest(trials),
            "trial_count": len(trials),
            "action_authority": False,
        },
    )
    return campaign


def _history(
    events: list[StatisticalSearchEvent],
) -> tuple[set[str], dict[str, dict], int]:
    proposed, observed, batches = set(), {}, 0
    for event in events:
        if event.event_type == "proposed":
            batches += 1
            proposed.update(item["trial_digest"] for item in event.detail["proposals"])
        elif event.event_type == "observed":
            observed.update(
                {item["trial_digest"]: item for item in event.detail["observations"]}
            )
    return proposed, observed, batches


def _numeric_vector(trial: dict, domains: dict[str, list]) -> list[float]:
    result = []
    for name in sorted(domains):
        values = domains[name]
        value = trial["parameters"][name]
        result.append(values.index(value) / max(1, len(values) - 1))
    return result


def _distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _stable_noise(seed: int, digest: str) -> float:
    raw = hashlib.sha256(f"{seed}:{digest}".encode()).digest()[:8]
    return int.from_bytes(raw, "big") / (2**64 - 1)


def _rank(
    campaign: StatisticalSearchCampaign,
    trials: list[dict],
    observed: dict[str, dict],
    universe: list[dict] | None = None,
) -> list[dict]:
    spec, method = campaign.specification, campaign.method
    seed, direction = spec["seed"], spec["objective"]["direction"]
    domains = {}
    universe = universe or trials
    for trial in universe:
        for name, value in trial["parameters"].items():
            domains.setdefault(name, [])
            if value not in domains[name]:
                domains[name].append(value)
    for values in domains.values():
        values.sort(key=lambda value: (str(type(value)), str(value)))
    vectors = {
        item["trial_digest"]: _numeric_vector(item, domains) for item in universe
    }
    completed = [
        (digest, item["objective_value"])
        for digest, item in observed.items()
        if item["status"] == "completed"
    ]
    scored = []
    for trial in trials:
        digest = trial["trial_digest"]
        noise = _stable_noise(seed, digest)
        if method == "exhaustive":
            score = -trial["ordinal"]
        elif method == "random":
            score = noise
        elif method == "structured":
            center = [0.5] * len(vectors[digest])
            score = _distance(vectors[digest], center) + noise * 1e-9
        elif method == "bayesian" and completed:
            weighted, total = 0.0, 0.0
            distances = []
            for prior_digest, value in completed:
                distance = _distance(vectors[digest], vectors[prior_digest])
                weight = 1 / (distance + 0.05)
                weighted += weight * value
                total += weight
                distances.append(distance)
            predicted = weighted / total
            if direction == "minimize":
                predicted = -predicted
            score = (
                predicted + spec["exploration_weight"] * min(distances) + noise * 1e-9
            )
        elif method == "evolutionary" and completed:
            best_digest, _ = max(
                completed,
                key=lambda item: item[1] if direction == "maximize" else -item[1],
            )
            score = -_distance(vectors[digest], vectors[best_digest]) + noise * 1e-6
        else:
            score = noise
        scored.append((score, digest, trial))
    return [item[2] for item in sorted(scored, key=lambda item: (-item[0], item[1]))]


def propose(
    db: Session, campaign_id
) -> tuple[StatisticalSearchCampaign, StatisticalSearchEvent, dict]:
    campaign = db.scalar(
        select(StatisticalSearchCampaign)
        .where(StatisticalSearchCampaign.id == campaign_id)
        .with_for_update()
    )
    if campaign is None:
        raise StatisticalSearchConflict("Search campaign not found.")
    if campaign.status != "active":
        raise StatisticalSearchConflict("Search campaign is terminal.")
    program = db.get(FactorExperimentProgram, campaign.factor_program_id)
    events = _events(db, campaign.id)
    proposed, observed, batches = _history(events)
    budget = campaign.specification["budget"]
    if (
        batches >= budget["maximum_batches"]
        or len(proposed) >= budget["maximum_evaluations"]
    ):
        campaign.status = "exhausted"
        raise StatisticalSearchConflict("Search budget is exhausted.")
    if proposed - set(observed):
        raise StatisticalSearchConflict(
            "Every prior proposal must be observed before another batch."
        )
    candidates = [
        trial
        for trial in program.compiled["trials"]
        if trial["trial_digest"] not in proposed
    ]
    count = min(
        budget["batch_size"],
        budget["maximum_evaluations"] - len(proposed),
        len(candidates),
    )
    selected = _rank(campaign, candidates, observed, program.compiled["trials"])[:count]
    history_digest = record_digest(
        [{"type": event.event_type, "digest": event.record_digest} for event in events]
    )
    detail = {
        "batch_number": batches + 1,
        "history_digest": history_digest,
        "proposals": selected,
        "budget_remaining": budget["maximum_evaluations"]
        - len(proposed)
        - len(selected),
    }
    event = _append(db, campaign, "proposed", detail)
    campaign.proposed_count += len(selected)
    return campaign, event, detail


def observe(
    db: Session, campaign_id, payload: SearchObservationBatch
) -> StatisticalSearchCampaign:
    campaign = db.scalar(
        select(StatisticalSearchCampaign)
        .where(StatisticalSearchCampaign.id == campaign_id)
        .with_for_update()
    )
    if campaign is None or campaign.status != "active":
        raise StatisticalSearchConflict("An active search campaign is required.")
    events = _events(db, campaign.id)
    proposed, observed, _ = _history(events)
    incoming = payload.model_dump(mode="json")["observations"]
    digests = [item["trial_digest"] for item in incoming]
    if len(digests) != len(set(digests)):
        raise StatisticalSearchConflict("Observation batch contains duplicate trials.")
    if any(digest not in proposed for digest in digests):
        raise StatisticalSearchConflict("Only proposed trials may be observed.")
    if any(digest in observed for digest in digests):
        raise StatisticalSearchConflict("A trial observation is immutable.")
    _append(db, campaign, "observed", {"observations": incoming})
    campaign.observed_count += len(incoming)
    if (
        campaign.observed_count
        == campaign.specification["budget"]["maximum_evaluations"]
    ):
        campaign.status = "complete"
        _append(
            db,
            campaign,
            "completed",
            {
                "reason": "fixed_evaluation_budget_consumed",
                "complete_history_digest": campaign.event_head_digest,
            },
        )
    return campaign


def cancel(
    db: Session, campaign_id, actor: str, reason: str
) -> StatisticalSearchCampaign:
    campaign = db.scalar(
        select(StatisticalSearchCampaign)
        .where(StatisticalSearchCampaign.id == campaign_id)
        .with_for_update()
    )
    if campaign is None or campaign.status != "active":
        raise StatisticalSearchConflict("An active search campaign is required.")
    campaign.status = "cancelled"
    _append(
        db,
        campaign,
        "cancelled",
        {"actor": actor, "reason": reason, "remaining_trials_are_not_results": True},
    )
    return campaign
