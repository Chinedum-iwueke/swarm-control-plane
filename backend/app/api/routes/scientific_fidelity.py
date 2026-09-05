from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.evidence import CanonicalEvidenceObject
from app.models.scientific_fidelity import (
    ScientificAdjudication,
    ScientificBenchmark,
    ScientificCorrectionProposal,
    ScientificFidelityManifest,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    FidelityManifestResponse,
    ScientificAdjudicationCreate,
    ScientificAdjudicationResponse,
    ScientificBenchmarkCreate,
    ScientificBenchmarkResponse,
    ScientificCorrectionCreate,
    ScientificCorrectionResponse,
    ScientificRepresentationCreate,
    ScientificRepresentationResponse,
)
from app.services.scientific_fidelity import (
    ScientificFidelityConflict,
    adjudicate_representation,
    create_benchmark,
    evaluate_benchmark,
    propose_correction,
    publish_manifest,
    register_representation,
)

router = APIRouter(
    prefix="/v1/research/scientific-fidelity",
    tags=["research-scientific-fidelity"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/representations", response_model=ScientificRepresentationResponse, status_code=201
)
def create_representation(
    payload: ScientificRepresentationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_representation(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/representations", response_model=list[ScientificRepresentationResponse])
def list_representations(
    db: Annotated[Session, Depends(get_db)], status: str | None = None
):
    query = select(ScientificRepresentation).order_by(
        ScientificRepresentation.created_at
    )
    if status:
        query = query.where(ScientificRepresentation.status == status)
    return list(db.scalars(query).all())


@router.get(
    "/representations/{representation_id}",
    response_model=ScientificRepresentationResponse,
)
def get_representation(
    representation_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    record = db.get(ScientificRepresentation, representation_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Scientific representation not found."
        )
    return record


@router.post("/manifests", response_model=FidelityManifestResponse, status_code=201)
def create_manifest(
    payload: FidelityManifestCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = publish_manifest(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/manifests", response_model=list[FidelityManifestResponse])
def list_manifests(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(ScientificFidelityManifest).order_by(
                ScientificFidelityManifest.created_at.desc()
            )
        ).all()
    )


@router.post(
    "/adjudications", response_model=ScientificAdjudicationResponse, status_code=201
)
def create_adjudication(
    payload: ScientificAdjudicationCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = adjudicate_representation(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/adjudications", response_model=list[ScientificAdjudicationResponse])
def list_adjudications(
    db: Annotated[Session, Depends(get_db)], representation_id: UUID | None = None
):
    query = select(ScientificAdjudication).order_by(
        ScientificAdjudication.created_at.desc()
    )
    if representation_id:
        query = query.where(
            ScientificAdjudication.representation_id == representation_id
        )
    return list(db.scalars(query).all())


@router.get("/review-queue")
def review_queue(db: Annotated[Session, Depends(get_db)], limit: int = 100):
    adjudicated = select(ScientificAdjudication.representation_id)
    query = (
        select(ScientificRepresentation)
        .where(
            ScientificRepresentation.status == "review_required",
            ScientificRepresentation.id.not_in(adjudicated),
        )
        .order_by(ScientificRepresentation.created_at)
        .limit(min(limit, 500))
    )
    records = list(db.scalars(query).all())
    result = []
    for record in records:
        benchmark = db.scalar(
            select(ScientificBenchmark)
            .where(
                ScientificBenchmark.representation_version
                == record.representation_version
            )
            .order_by(ScientificBenchmark.created_at.desc())
        )
        item = ScientificRepresentationResponse.model_validate(record).model_dump(
            mode="json"
        )
        item["corpus_digest"] = benchmark.corpus_digest if benchmark else None
        result.append(item)
    return result


@router.get("/review-context/{representation_id}")
def review_context(representation_id: UUID, db: Annotated[Session, Depends(get_db)]):
    representation = db.get(ScientificRepresentation, representation_id)
    if representation is None:
        raise HTTPException(
            status_code=404, detail="Scientific representation not found."
        )
    source = db.get(CanonicalEvidenceObject, representation.source_object_id)
    labels = list(
        db.scalars(
            select(ScientificAdjudication)
            .where(ScientificAdjudication.representation_id == representation_id)
            .order_by(ScientificAdjudication.created_at)
        ).all()
    )
    return {
        "representation": ScientificRepresentationResponse.model_validate(
            representation
        ).model_dump(mode="json"),
        "source": {
            "object_id": str(source.id),
            "payload": source.payload,
            "content_digest": source.content_digest,
        }
        if source
        else None,
        "adjudications": [
            ScientificAdjudicationResponse.model_validate(item).model_dump(mode="json")
            for item in labels
        ],
        "conflicted": len({item.decision for item in labels}) > 1,
    }


@router.post("/benchmarks", response_model=ScientificBenchmarkResponse, status_code=201)
def register_benchmark(
    payload: ScientificBenchmarkCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = create_benchmark(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/benchmarks/{benchmark_id}/evaluate", response_model=ScientificBenchmarkResponse
)
def run_benchmark_evaluation(
    benchmark_id: UUID, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = evaluate_benchmark(db, benchmark_id)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/benchmarks", response_model=list[ScientificBenchmarkResponse])
def list_benchmarks(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(ScientificBenchmark).order_by(ScientificBenchmark.created_at.desc())
        ).all()
    )


@router.post(
    "/corrections", response_model=ScientificCorrectionResponse, status_code=201
)
def create_correction(
    payload: ScientificCorrectionCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = propose_correction(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except ScientificFidelityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/corrections", response_model=list[ScientificCorrectionResponse])
def list_corrections(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(ScientificCorrectionProposal).order_by(
                ScientificCorrectionProposal.created_at.desc()
            )
        ).all()
    )
