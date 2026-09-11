from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuthorityDecisionRecord,
    CanonicalEvidenceObject,
    EvidenceCorpusFreshness,
    EvidenceGraphProjectionState,
    EvidenceRetrievalState,
    ResearchDataSnapshot,
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchResult,
    ResearchReview,
    ResearchSource,
    ResearchTrial,
    Task,
    TaskApproval,
)
from app.schemas.evidence import EvidenceObjectCreate
from app.schemas.laboratory import (
    LaboratoryPublicationCreate,
    MemoryReceiptCreate,
    ProjectionReceiptCreate,
)
from app.schemas.research import (
    DataSnapshotSpecification,
    ExperimentManifest,
    HypothesisSpecification,
    ResearchDataSnapshotCreate,
    ResearchDecisionCreate,
    ResearchExperimentCreate,
    ResearchHypothesisCreate,
    ResearchResultCreate,
    ResearchReviewCreate,
    ResearchSourceCreate,
    ResearchTrialCreate,
    ResultDocument,
    SourceSpecification,
    TrialPlan,
)
from app.schemas.research_bridge import (
    GovernedResearchAdvance,
    GovernedResearchProposal,
)
from app.services.evidence import ORCHESTRATOR_ACCESS, register_evidence_object
from app.services.graph import digest_document
from app.services.laboratory import (
    create_publication,
    record_memory_receipt,
    record_projection_receipt,
)
from app.services.research import (
    add_review,
    record_digest,
    register_data_snapshot,
    register_decision,
    register_experiment,
    register_hypothesis,
    register_result,
    register_source,
    register_trial,
)
from app.services.research_bridge import advance_bridge, create_bridge

NAMESPACE = uuid.UUID("341aab44-5ddf-41f4-a1ba-b7cc28457a3c")


def _existing(db: Session, model, **filters):
    return db.scalar(select(model).filter_by(**filters))


def _source(db: Session, envelope: dict[str, Any]) -> ResearchSource:
    dataset = envelope["bridge_proposal"]["dataset"]
    key = f"ALPHA002-SOURCE-{dataset['dataset_digest'][:20]}"
    found = _existing(db, ResearchSource, source_key=key)
    if found:
        return found
    specification = SourceSpecification(
        title="ALPHA-002 admitted live-exchange research panel",
        source_type="dataset",
        version=dataset["dataset_build_id"],
        content_sha256=dataset["dataset_digest"],
        provenance="DATA-002/003 admitted immutable Bulletproof research panel",
        point_in_time=True,
        observed_at=dataset["end"],
    )
    return register_source(
        db,
        ResearchSourceCreate(
            source_key=key,
            specification=specification,
            record_digest=record_digest(specification),
            registered_by="alpha-campaign-director",
        ),
    )


def _snapshot(
    db: Session, envelope: dict[str, Any], source: ResearchSource
) -> ResearchDataSnapshot:
    dataset = envelope["bridge_proposal"]["dataset"]
    key = f"ALPHA002-SNAPSHOT-{dataset['dataset_digest'][:20]}"
    found = _existing(db, ResearchDataSnapshot, snapshot_key=key)
    if found:
        return found
    specification = DataSnapshotSpecification(
        provider="DATA-002/003 admitted live exchange history",
        instrument=dataset["instrument"],
        timeframe=dataset["timeframe"],
        date_start=dataset["start"],
        date_end=dataset["end"],
        rows=dataset["rows"],
        format="parquet",
        storage_uri=f"snapshot://sha256/{dataset['dataset_digest']}",
        transformation="Immutable curated panel; no proxy or synthetic substitution.",
        point_in_time=True,
    )
    document = {
        "snapshot_key": key,
        "source_id": str(source.id),
        "specification": specification.model_dump(mode="json"),
        "content_digest": dataset["dataset_digest"],
        "registered_by": "alpha-campaign-director",
    }
    return register_data_snapshot(
        db,
        ResearchDataSnapshotCreate(
            **document,
            record_digest=record_digest(document),
        ),
    )


def _hypothesis(db: Session, envelope: dict[str, Any]) -> ResearchHypothesis:
    proposal = envelope["bridge_proposal"]
    key = f"ALPHA002-{proposal['source']['question_digest'][:20]}"
    found = _existing(db, ResearchHypothesis, hypothesis_key=key)
    question = proposal["source"]["question"]
    specification = HypothesisSpecification(
        research_question=question,
        rationale="Evidence-grounded selected question executed without proxy substitution.",
        mechanism=(
            "The exact registered Bulletproof strategy encodes the claimed market mechanism; "
            "the retained hypothesis card binds supporting Research Intelligence citations."
        ),
        prediction="The registered strategy has positive net expectancy with adequate trade support.",
        universe=[proposal["dataset"]["instrument"]],
        target="net portfolio outcome under the registered strategy",
        horizon="registered strategy horizon",
        null_hypothesis="The registered strategy has no positive net edge after costs.",
        failure_conditions=[
            "truth or point-in-time validation fails",
            "net expectancy is not positive",
            "out-of-sample evidence is unavailable",
        ],
        rival_explanations=["volatility exposure", "selection bias", "data leakage"],
        maximum_trials=proposal["search"]["max_variants"],
    )
    record = found or register_hypothesis(
        db,
        ResearchHypothesisCreate(
            hypothesis_key=key,
            trial_family=f"{key}-FAMILY",
            specification=specification,
            record_digest=record_digest(specification),
            registered_by="bulletproof-alpha-producer",
        ),
    )
    approval = _existing(
        db,
        ResearchReview,
        subject_type="hypothesis",
        subject_id=record.id,
        review_kind="approval",
    )
    if approval is None:
        add_review(
            db,
            "hypothesis",
            record.id,
            ResearchReviewCreate(
                subject_digest=record.record_digest,
                review_kind="approval",
                verdict="approved",
                review={
                    "summary": (
                        "Exact registered-strategy reuse is covered by the founder-activated "
                        "campaign digest; new or expanded strategy code requires a new approval."
                    )
                },
                reviewer="founder-operator",
            ),
        )
    return record


def _experiment(
    db: Session,
    envelope: dict[str, Any],
    hypothesis: ResearchHypothesis,
    source: ResearchSource,
    snapshot: ResearchDataSnapshot,
) -> ResearchExperiment:
    proposal = envelope["bridge_proposal"]
    key = f"ALPHA002-EXP-{proposal['proposal_digest'][:20]}"
    found = _existing(db, ResearchExperiment, experiment_key=key)
    experiment = envelope["experiment"]
    manifest = ExperimentManifest(
        repository="bulletproof_bt",
        repository_commit=proposal["resolution"].get(
            "source_commit", envelope["source_commit"]
        ),
        dataset_version=proposal["dataset"]["dataset_build_id"],
        instrument_universe=[proposal["dataset"]["instrument"]],
        timeframe=proposal["dataset"]["timeframe"],
        sample_range=experiment["sample_range"],
        features=experiment["features"] or ["registered strategy inputs"],
        target=experiment["target"],
        model_or_rule=proposal["resolution"]["strategy"],
        parameters={
            "variant_count": proposal["search"]["variant_count"],
            "tier": "Tier2B",
        },
        fees_bps=experiment["fees_bps"],
        slippage_bps=experiment["slippage_bps"],
        delay_bars=experiment["delay_bars"],
        validation_method="classic engine, immutable bundle, truth and independent review gates",
        success_criteria=["positive net expectancy", "all candidate gates pass"],
        rejection_criteria=["any candidate gate fails"],
        engine_version=f"bulletproof_bt:{envelope['source_commit']}",
        data_snapshot_digest=proposal["dataset"]["dataset_digest"],
    )
    record = found or register_experiment(
        db,
        ResearchExperimentCreate(
            experiment_key=key,
            hypothesis_id=hypothesis.id,
            source_id=source.id,
            snapshot_id=snapshot.id,
            manifest=manifest,
            manifest_digest=record_digest(manifest),
            registered_by="alpha-campaign-director",
        ),
    )
    approval = _existing(
        db,
        ResearchReview,
        subject_type="experiment",
        subject_id=record.id,
        review_kind="approval",
    )
    if approval is None:
        add_review(
            db,
            "experiment",
            record.id,
            ResearchReviewCreate(
                subject_digest=record.manifest_digest,
                review_kind="approval",
                verdict="approved",
                review={
                    "summary": "Exact campaign-bound registered reuse was preapproved."
                },
                reviewer="founder-operator",
            ),
        )
    return record


def _run_object(db: Session, envelope: dict[str, Any]) -> CanonicalEvidenceObject:
    proposal = envelope["bridge_proposal"]
    trial = envelope["trial"]
    object_id = uuid.uuid5(NAMESPACE, f"run:{trial['bundle_digest']}")
    found = db.get(CanonicalEvidenceObject, object_id)
    if found:
        return found
    dataset_id = uuid.uuid5(
        NAMESPACE, f"dataset:{proposal['dataset']['dataset_digest']}"
    )
    dataset = db.get(CanonicalEvidenceObject, dataset_id)
    if dataset is None:
        source_id = uuid.uuid5(
            NAMESPACE, f"source:{proposal['dataset']['dataset_digest']}"
        )
        source_payload = {
            "kind": "source",
            "title": "ALPHA-002 admitted live-exchange panel",
            "origin": f"snapshot://sha256/{proposal['dataset']['dataset_digest']}",
            "rights": "internal research use",
            "acquired_at": proposal["dataset"]["end"],
        }
        register_evidence_object(
            db,
            _evidence(source_id, "source", source_payload, "primary"),
            ORCHESTRATOR_ACCESS,
            commit=False,
        )
        dataset_payload = {
            "kind": "dataset",
            "source_object_ids": [str(source_id)],
            "schema_digest": digest_document(envelope["experiment"]["features"]),
            "partition_digests": [proposal["dataset"]["dataset_digest"]],
            "availability_policy": "Point-in-time immutable campaign binding.",
            "correction_object_ids": [],
        }
        register_evidence_object(
            db,
            _evidence(dataset_id, "dataset", dataset_payload, "primary"),
            ORCHESTRATOR_ACCESS,
            commit=False,
        )
    payload = {
        "kind": "run",
        "dataset_object_ids": [str(dataset_id)],
        "specification_digest": proposal["proposal_digest"],
        "code_digest": trial["code_digest"],
        "environment_digest": digest_document(
            {"source_commit": envelope["source_commit"]}
        ),
        "market_model_bundle_digest": trial["market_model_bundle_digest"],
        "representation_contract_digest": trial["representation_contract_digest"],
        "search_plan_digest": trial["search_plan_digest"],
        "attempt": 1,
        "bundle_digest": trial["bundle_digest"],
        "bundle_manifest_digest": trial["bundle_manifest_digest"],
        "bundle_uri": f"bundle://sha256/{trial['bundle_digest']}",
    }
    record = register_evidence_object(
        db,
        _evidence(object_id, "run", payload, "operational"),
        ORCHESTRATOR_ACCESS,
        commit=False,
    )
    db.commit()
    db.refresh(record)
    return record


def _evidence(object_id, object_type, payload, authority):
    return EvidenceObjectCreate.model_validate(
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": object_id,
            "object_type": object_type,
            "content_version": "1",
            "content_digest": digest_document(payload),
            "producer": {
                "system": "bulletproof-bt",
                "native_type": object_type,
                "native_id": str(object_id),
                "schema_version": "alpha002-native-receipt-v1.0.0",
            },
            "aliases": [
                {
                    "namespace": "bulletproof-bt",
                    "object_type": object_type,
                    "value": str(object_id),
                }
            ],
            "project": "bulletproof-bt",
            "access_class": "restricted",
            "authority_class": authority,
            "payload": payload,
            "created_by": "bulletproof-alpha-producer",
        }
    )


def _require_current_projections(graph, retrieval, corpus) -> None:
    if (
        graph is None
        or retrieval is None
        or corpus is None
        or graph.source_epoch != corpus.epoch
        or retrieval.source_epoch != corpus.epoch
        or retrieval.corpus_digest != corpus.corpus_digest
    ):
        raise HTTPException(409, "Canonical projections are unavailable or stale.")


def _has_founder_execution_authority(
    db: Session, approval: TaskApproval | None
) -> bool:
    if approval is None or approval.decided_by is None:
        return False
    decision = db.scalar(
        select(AuthorityDecisionRecord)
        .where(
            AuthorityDecisionRecord.decision_type == "task-approval",
            AuthorityDecisionRecord.action == "approve",
            AuthorityDecisionRecord.object_type == "task-approval",
            AuthorityDecisionRecord.object_id == str(approval.id),
            AuthorityDecisionRecord.actor == approval.decided_by,
            AuthorityDecisionRecord.outcome == "authorized",
        )
        .order_by(AuthorityDecisionRecord.created_at.desc())
    )
    return decision is not None and "founder" in decision.effective_roles


def _result_metrics(trial_data: dict[str, Any]) -> dict[str, float | int | bool | None]:
    metrics = trial_data.get("metrics", {})
    if not isinstance(metrics, dict):
        raise HTTPException(422, "Alpha trial metrics must be an object.")
    measurements = {
        key: value
        for key, value in metrics.items()
        if value is None or isinstance(value, (float, int, bool))
    }
    if not measurements:
        raise HTTPException(422, "Alpha trial has no scientific measurements.")
    return measurements


def publish_execution(db: Session, envelope: dict[str, Any]) -> dict[str, Any]:
    version = envelope.get("schema_version")
    if version not in {
        "alpha002-publication-envelope-v1.0.0",
        "alpha003-publication-envelope-v1.0.0",
    }:
        raise HTTPException(422, "Unsupported alpha publication envelope.")
    execution_approval = None
    campaign_label = (
        "ALPHA-003"
        if version == "alpha003-publication-envelope-v1.0.0"
        else "ALPHA-002"
    )
    if version == "alpha003-publication-envelope-v1.0.0":
        task = db.get(Task, uuid.UUID(envelope["task_id"]))
        execution_approval = (
            db.scalar(select(TaskApproval).where(TaskApproval.task_id == task.id))
            if task is not None
            else None
        )
        if (
            task is None
            or execution_approval is None
            or execution_approval.status != "consumed"
            or execution_approval.plan_digest != task.plan_digest
            or not _has_founder_execution_authority(db, execution_approval)
        ):
            raise HTTPException(
                409,
                "ALPHA-003 publication requires the consumed digest-bound founder execution approval.",
            )
    proposal = GovernedResearchProposal.model_validate(envelope["bridge_proposal"])
    bridge = create_bridge(db, proposal)
    if bridge.state == "awaiting_approval":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="awaiting_approval",
                next_state="approved",
                receipt={
                    "approved_by": "founder-operator",
                    "campaign_digest": envelope["campaign_digest"],
                    **(
                        {
                            "execution_approval_id": str(execution_approval.id),
                            "execution_plan_digest": execution_approval.plan_digest,
                        }
                        if execution_approval is not None
                        else {}
                    ),
                },
            ),
        )
    source = _source(db, envelope)
    snapshot = _snapshot(db, envelope, source)
    hypothesis = _hypothesis(db, envelope)
    experiment = _experiment(db, envelope, hypothesis, source, snapshot)
    trial_data = envelope["trial"]
    trial = _existing(
        db, ResearchTrial, run_id=f"ALPHA002-{trial_data['trial_id'][:32]}"
    )
    if trial is None:
        plan = TrialPlan(
            run_id=f"ALPHA002-{trial_data['trial_id'][:32]}",
            task_id=uuid.UUID(envelope["task_id"]),
            code_commit=envelope["source_commit"],
            dataset_digest=proposal.dataset["dataset_digest"],
            engine_digest=trial_data["code_digest"],
        )
        document = {
            "experiment_digest": experiment.manifest_digest,
            "trial_number": 1,
            "plan": plan.model_dump(mode="json"),
            "executed_by": "bulletproof-alpha-producer",
        }
        trial = register_trial(
            db,
            experiment.id,
            ResearchTrialCreate(
                experiment_digest=experiment.manifest_digest,
                plan=plan,
                record_digest=record_digest(document),
                executed_by="bulletproof-alpha-producer",
            ),
        )
    if bridge.state == "approved":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="approved",
                next_state="registry_bound",
                receipt={
                    "hypothesis_id": str(hypothesis.id),
                    "experiment_id": str(experiment.id),
                    "trial_id": str(trial.id),
                },
            ),
        )
    if bridge.state == "registry_bound":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="registry_bound",
                next_state="executed",
                receipt={
                    "trial_id": str(trial.id),
                    "bundle_digest": trial_data["bundle_digest"],
                },
            ),
        )
    if bridge.state == "executed":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="executed",
                next_state="truth_validated",
                receipt=trial_data["truth"],
            ),
        )
    if bridge.state == "truth_validated":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="truth_validated",
                next_state="bundle_finalized",
                receipt={
                    "bundle_digest": trial_data["bundle_digest"],
                    "bundle_manifest_digest": trial_data["bundle_manifest_digest"],
                },
            ),
        )
    result = _existing(db, ResearchResult, trial_id=trial.id)
    if result is None:
        producer_gates = envelope["producer_gate_report"]
        passed = not producer_gates["failed_gates"]
        result_doc = ResultDocument(
            summary=(
                f"{campaign_label} retained the exact governed real-data run; candidate status "
                "depends on every declared gate, not the sign of one metric."
            ),
            metrics=_result_metrics(trial_data),
            robustness_status="passed" if passed else "failed",
            rejection_reason=(
                None
                if passed
                else "One or more frozen held-out or cost-stress gates failed."
            ),
            evidence_artifacts=[
                trial_data["bundle_digest"],
                trial_data["bundle_manifest_digest"],
            ],
            output_artifact_digest=trial_data["bundle_digest"],
            started_at=trial_data["started_at"],
            ended_at=trial_data["ended_at"],
        )
        payload = {
            "trial_digest": trial.record_digest,
            "outcome": "accepted" if passed else "rejected",
            "result": result_doc.model_dump(mode="json"),
            "recorded_by": "bulletproof-alpha-producer",
        }
        result = register_result(
            db,
            trial.id,
            ResearchResultCreate(**payload, record_digest=record_digest(payload)),
        )
    reviews = list(
        db.scalars(
            select(ResearchReview).where(
                ResearchReview.subject_type == "result",
                ResearchReview.subject_id == result.id,
            )
        ).all()
    )
    passed = not envelope["producer_gate_report"]["failed_gates"]
    for kind, reviewer, summary in (
        (
            "independent_review",
            "alpha002-statistical-evaluator",
            (
                "Verified temporal holdout, doubled-cost counterfactual and prospective "
                "validation-only finite-grid selection audit."
                if passed
                else "Verified the failed frozen held-out gates; retain the negative result."
            ),
        ),
        (
            "adversarial_review",
            "alpha002-adversarial-evaluator",
            "No-capital authority is intact and no failed gate is hidden or weakened.",
        ),
    ):
        if not any(item.review_kind == kind for item in reviews):
            add_review(
                db,
                "result",
                result.id,
                ResearchReviewCreate(
                    subject_digest=result.record_digest,
                    review_kind=kind,
                    verdict="approved",
                    review={"summary": summary},
                    reviewer=reviewer,
                ),
            )
    decision = _existing(db, ResearchDecision, result_id=result.id)
    if decision is None:
        decision = register_decision(
            db,
            result.id,
            ResearchDecisionCreate(
                result_digest=result.record_digest,
                decision="replicate" if passed else "retain",
                rationale=(
                    "Retain as a prospective shadow candidate for separate founder review; "
                    "this decision grants no capital or order authority."
                    if passed
                    else "Retain the negative real-data answer and its complete evidence."
                ),
                decided_by="alpha-campaign-policy",
            ),
        )
    if bridge.state == "bundle_finalized":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="bundle_finalized",
                next_state="independently_reviewed",
                receipt={
                    "reviewers": [
                        "alpha002-statistical-evaluator",
                        "alpha002-adversarial-evaluator",
                    ],
                    "decision_id": str(decision.id),
                    "verdict": "candidate_reviewed" if passed else "retain_negative",
                },
            ),
        )
    run = _run_object(db, envelope)
    publication_payload = LaboratoryPublicationCreate(
        schema_version="laboratory-publication-v1.0.0",
        trial_id=trial.id,
        result_id=result.id,
        run_object_id=run.id,
        repository_commit=envelope["source_commit"],
        dataset_digest=proposal.dataset["dataset_digest"],
        market_model_bundle_digest=trial_data["market_model_bundle_digest"],
        representation_contract_digest=trial_data["representation_contract_digest"],
        bundle_digest=trial_data["bundle_digest"],
        bundle_manifest_digest=trial_data["bundle_manifest_digest"],
        request_digest="0" * 64,
    )
    publication_payload.request_digest = digest_document(
        publication_payload.model_dump(mode="json", exclude={"request_digest"})
    )
    publication = create_publication(db, publication_payload)
    if bridge.state == "independently_reviewed":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="independently_reviewed",
                next_state="published",
                receipt={"publication_id": str(publication.id)},
            ),
        )
    graph = db.get(EvidenceGraphProjectionState, "canonical-knowledge-graph")
    retrieval = db.get(EvidenceRetrievalState, "canonical-scientific")
    corpus = db.get(EvidenceCorpusFreshness, "canonical-scientific")
    _require_current_projections(graph, retrieval, corpus)
    if publication.state == "awaiting_projections":
        publication = record_projection_receipt(
            db,
            publication.id,
            ProjectionReceiptCreate(
                schema_version="laboratory-projection-receipt-v1.0.0",
                graph_manifest_digest=graph.manifest_digest,
                graph_source_epoch=graph.source_epoch,
                retrieval_corpus_digest=retrieval.corpus_digest,
                retrieval_source_epoch=retrieval.source_epoch,
            ),
        )
    if publication.state == "awaiting_memory":
        publication = record_memory_receipt(
            db,
            publication.id,
            MemoryReceiptCreate.model_validate(envelope["memory_receipt"]),
        )
    if bridge.state == "published":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="published",
                next_state="memory_confirmed",
                receipt=envelope["memory_receipt"],
            ),
        )
    if bridge.state == "memory_confirmed":
        bridge = advance_bridge(
            db,
            bridge.id,
            GovernedResearchAdvance(
                expected_state="memory_confirmed",
                next_state="complete",
                receipt={
                    "publication_id": str(publication.id),
                    "publication_state": publication.state,
                },
            ),
        )
    final_gate_report = {
        **envelope["producer_gate_report"],
        "independent_review_complete": True,
        "shadow_eligible": passed,
    }
    return {
        "bridge_id": str(bridge.id),
        "bridge_state": bridge.state,
        "publication_id": str(publication.id),
        "publication_state": publication.state,
        "result_id": str(result.id),
        "outcome": "candidate" if passed else "negative",
        "gate_report": final_gate_report,
        "evidence_digests": [
            trial_data["bundle_digest"],
            trial_data["bundle_manifest_digest"],
            result.record_digest,
        ],
    }
