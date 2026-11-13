"""Read-only candidate dispositions, independent of the campaign's current cursor."""

from sqlalchemy import String, cast, func, literal, select, union_all

from app.models.alpha_campaign import AlphaCampaign, AlphaCampaignAttempt, AlphaCampaignEvent


BLOCKERS = {
    "resolve_native_requirements_feasibility": (
        "Native requirements planner", "Feasible smoke/scientific windows and sufficient composed feature history",
        "Publish a bounded, reviewed requirements or coverage successor; unchanged inputs reuse the retained result.",
    ),
    "repair_native_requirements_feasibility": (
        "Native admission runtime", "Successful pinned-source feasibility receipt",
        "Repair the native planner runtime and publish an authorized successor; do not retry unchanged failures automatically.",
    ),
    "produce_admitted_predictor_coverage": (
        "Native data admission", "Candidate-specific predictor coverage and availability receipts",
        "Obtain exact candidate coverage and independently reviewed requirements.",
    ),
    "scientific_requirements_rejected": (
        "Representation and requirements planning", "Acceptable scientific requirements and feasibility evidence",
        "Publish a corrected immutable successor and obtain independent review.",
    ),
    "restore_requirements_producer_identity": (
        "Native data admission", "Lease-time producer identity",
        "Complete bounded admission re-attestation without rewriting the original lease.",
    ),
    "repair_scientific_requirements_evidence": (
        "Requirements planning", "Valid coverage and producer custody",
        "Repair the evidence in a reviewed immutable successor.",
    ),
    "renew_weekly_research_mandate": (
        "Research authority", "An applicable active mandate",
        "Reconcile existing authority or obtain exact-digest founder approval.",
    ),
}


def project(campaign, attempt=None, event=None):
    source = None
    if attempt is None:
        queue = campaign.specification.get("research_queue", [])
        if campaign.hypothesis_count >= len(queue):
            return None
        source = queue[campaign.hypothesis_count]
    payload = event.payload if event is not None else {}
    gates = attempt.gate_report.get("failed_gates", []) if attempt else []
    reason = payload.get("reason") or (gates[0] if gates else (campaign.terminal_reason.get("category") or campaign.next_action))
    classification = reason if reason in BLOCKERS else campaign.next_action if not attempt else reason
    owner, missing, retry = BLOCKERS.get(classification, (
        "Not recorded", "Not recorded", "Review the retained blocker and evidence before reconsideration."
    ))
    return {
        "id": str(attempt.id if attempt else campaign.id),
        "status": "deferred" if attempt else "blocked",
        "campaign_id": str(campaign.id), "campaign_key": campaign.campaign_key,
        "question": attempt.question if attempt else source["question"],
        "source_candidate_id": str(attempt.source_candidate_id if attempt else source["source_candidate_id"]),
        "reason": reason,
        "detail": payload.get("detail", {}) if attempt else campaign.terminal_reason,
        "missing_evidence": missing,
        "responsible_component": owner,
        "owner_basis": "blocker classification" if classification in BLOCKERS else "not recorded",
        "retry_condition": payload.get("retry_condition") or (gates[1] if len(gates) > 1 else retry),
        "evidence_digests": attempt.evidence_digests if attempt else [],
        "trial_count": attempt.trial_count if attempt else 0,
        "scientific_result": False,
        "updated_at": attempt.created_at if attempt else campaign.heartbeat_at,
        "history_retained": True,
    }


def overview(db, *, category="all", query="", offset=0, limit=25):
    deferred = select(
        cast(AlphaCampaignAttempt.id, String).label("record_id"),
        literal("deferred").label("kind"), AlphaCampaignAttempt.question.label("question"),
        AlphaCampaignAttempt.created_at.label("updated_at"),
    ).where(AlphaCampaignAttempt.outcome == "deferred")
    question = AlphaCampaign.specification["research_queue"].op("->")(
        AlphaCampaign.hypothesis_count
    ).op("->>")("question")
    blocked = select(
        cast(AlphaCampaign.id, String).label("record_id"), literal("blocked").label("kind"),
        question.label("question"), AlphaCampaign.heartbeat_at.label("updated_at"),
    ).where(AlphaCampaign.status == "needs_attention", question.is_not(None))
    records = union_all(deferred, blocked).subquery()
    filters = []
    if category != "all":
        filters.append(records.c.kind == category)
    if query.strip():
        filters.append(records.c.question.icontains(query.strip(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(records).where(*filters)) or 0
    page = db.execute(select(records).where(*filters).order_by(
        records.c.updated_at.desc(), records.c.kind, records.c.record_id
    ).offset(offset).limit(limit)).mappings().all()
    attempt_ids = [row["record_id"] for row in page if row["kind"] == "deferred"]
    attempts = {str(item.id): item for item in db.scalars(select(AlphaCampaignAttempt).where(
        AlphaCampaignAttempt.id.in_(attempt_ids)
    )).all()} if attempt_ids else {}
    campaign_ids = {str(item.campaign_id) for item in attempts.values()} | {
        row["record_id"] for row in page if row["kind"] == "blocked"
    }
    campaigns = {str(item.id): item for item in db.scalars(select(AlphaCampaign).where(
        AlphaCampaign.id.in_(campaign_ids)
    )).all()} if campaign_ids else {}
    events = {}
    if attempts:
        for event in db.scalars(select(AlphaCampaignEvent).where(
            AlphaCampaignEvent.campaign_id.in_(campaign_ids),
            AlphaCampaignEvent.event_type == "candidate_deferred",
            AlphaCampaignEvent.payload["source_candidate_id"].astext.in_(
                [str(item.source_candidate_id) for item in attempts.values()]
            ),
        ).order_by(AlphaCampaignEvent.sequence.desc())).all():
            events.setdefault((str(event.campaign_id), event.payload["source_candidate_id"]), event)
    items = []
    for row in page:
        attempt = attempts.get(row["record_id"]) if row["kind"] == "deferred" else None
        campaign_id = str(attempt.campaign_id) if attempt else row["record_id"]
        campaign = campaigns.get(campaign_id)
        if campaign is None:
            continue
        event = events.get((campaign_id, str(attempt.source_candidate_id))) if attempt else None
        item = project(campaign, attempt, event)
        if item:
            items.append(item)
    return {"items": items, "total": total, "offset": offset, "limit": limit,
            "has_more": offset + limit < total}
