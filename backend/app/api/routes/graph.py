from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.graph import (
    CanonicalEdgeCreate,
    CanonicalEdgeResponse,
    CognitiveToolRequest,
    CognitiveToolResponse,
    ContextPackRequest,
    ContextPackResponse,
    GraphProjectionResponse,
    GraphQueryRequest,
    GraphQueryResponse,
)
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.graph import (
    assemble_context_pack,
    build_graph_projection,
    execute_cognitive_tool,
    graph_overview,
    graph_projection_status,
    query_graph,
    register_edge,
)

router = APIRouter(
    prefix="/v1/research/graph",
    tags=["canonical-knowledge-graph"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/edges", response_model=CanonicalEdgeResponse, status_code=201)
def create_edge(
    payload: CanonicalEdgeCreate, db: Annotated[Session, Depends(get_db)]
):
    record = register_edge(db, payload, ORCHESTRATOR_ACCESS)
    return CanonicalEdgeResponse(
        id=record.id,
        **payload.model_dump(),
        record_digest=record.record_digest,
        created_at=record.created_at,
    )


@router.post("/projections/rebuild", response_model=GraphProjectionResponse)
def rebuild_graph(db: Annotated[Session, Depends(get_db)]):
    state = build_graph_projection(db)
    return GraphProjectionResponse.model_validate(state, from_attributes=True)


@router.get("/projections/status", response_model=GraphProjectionResponse)
def graph_status(db: Annotated[Session, Depends(get_db)]):
    state, stale = graph_projection_status(db)
    return GraphProjectionResponse(
        projection_name=state.projection_name,
        projection_version=state.projection_version,
        corpus_digest=state.corpus_digest,
        source_epoch=state.source_epoch,
        node_count=state.node_count,
        edge_count=state.edge_count,
        manifest_digest=state.manifest_digest,
        built_at=state.built_at,
        stale=stale,
    )


@router.post("/query", response_model=GraphQueryResponse)
def graph_query(
    payload: GraphQueryRequest, db: Annotated[Session, Depends(get_db)]
):
    return query_graph(db, payload, ORCHESTRATOR_ACCESS)


@router.get("/overview", response_model=GraphQueryResponse)
def read_graph_overview(
    db: Annotated[Session, Depends(get_db)],
    project: str | None = Query(default=None, pattern=r"^[a-z][a-z0-9._-]{0,99}$"),
    limit: int = Query(default=100, ge=1, le=500),
):
    return graph_overview(db, ORCHESTRATOR_ACCESS, project=project, limit=limit)


@router.post("/context-packs", response_model=ContextPackResponse)
def create_context_pack(
    payload: ContextPackRequest, db: Annotated[Session, Depends(get_db)]
):
    return assemble_context_pack(db, payload, ORCHESTRATOR_ACCESS)


@router.post("/tools/execute", response_model=CognitiveToolResponse)
def execute_tool(
    payload: CognitiveToolRequest, db: Annotated[Session, Depends(get_db)]
):
    receipt = execute_cognitive_tool(db, payload, ORCHESTRATOR_ACCESS)
    return CognitiveToolResponse(
        receipt_id=receipt.id,
        tool=receipt.tool_name,
        tool_version=receipt.tool_version,
        input_digest=receipt.input_digest,
        result=receipt.result,
        output_digest=receipt.output_digest,
        context_pack_digest=receipt.context_pack_digest,
        receipt_digest=receipt.receipt_digest,
        created_at=receipt.created_at,
    )
