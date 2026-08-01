from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_agent
from app.db.session import get_db
from app.models import Agent, PackageDeployment, RolePackage
from app.schemas.research import (
    AgentResearchBriefCreate,
    AgentResearchExperimentCreate,
    AgentResearchHypothesisCreate,
    AgentResearchResultCreate,
    AgentResearchReviewCreate,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ResearchBriefCreate,
    ResearchBriefResponse,
    ResearchExperimentCreate,
    ResearchExperimentResponse,
    ResearchHypothesisCreate,
    ResearchHypothesisResponse,
    ResearchResultCreate,
    ResearchResultResponse,
    ResearchReviewCreate,
    ResearchReviewResponse,
)
from app.services.research import (
    add_review,
    create_brief,
    register_experiment,
    register_hypothesis,
    register_result,
    search_knowledge,
)

router = APIRouter(prefix="/v1/agent/research", tags=["agent-research"])


def _require_role(
    db: Session, agent: Agent, *, capability: str, package_name: str
) -> None:
    if capability not in agent.capabilities:
        raise HTTPException(status_code=403, detail="Agent lacks required capability.")
    package = db.scalar(
        select(RolePackage)
        .join(PackageDeployment, PackageDeployment.package_id == RolePackage.id)
        .where(
            PackageDeployment.agent_id == agent.id,
            PackageDeployment.is_active.is_(True),
            RolePackage.name == package_name,
        )
    )
    if package is None or capability not in package.manifest.get(
        "required_capabilities", []
    ):
        raise HTTPException(
            status_code=409,
            detail="Required role package is not actively deployed.",
        )


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
def agent_knowledge_search(
    payload: KnowledgeSearchRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_role(
        db,
        agent,
        capability="knowledge-retrieval",
        package_name="m13-senior-research-specialist",
    )
    return KnowledgeSearchResponse.model_validate(
        search_knowledge(db, payload.query, payload.limit, payload.evidence_types)
    )


@router.post("/briefs", response_model=ResearchBriefResponse, status_code=201)
def create_agent_brief(
    payload: AgentResearchBriefCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_role(
        db,
        agent,
        capability="research-proposal",
        package_name="m13-senior-research-specialist",
    )
    record = create_brief(
        db,
        ResearchBriefCreate(**payload.model_dump(), created_by=agent.slug),
    )
    return ResearchBriefResponse.model_validate(record)


@router.post("/hypotheses", response_model=ResearchHypothesisResponse, status_code=201)
def create_agent_hypothesis(
    payload: AgentResearchHypothesisCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_role(
        db,
        agent,
        capability="research-proposal",
        package_name="m13-senior-research-specialist",
    )
    record = register_hypothesis(
        db,
        ResearchHypothesisCreate(**payload.model_dump(), registered_by=agent.slug),
    )
    return ResearchHypothesisResponse.model_validate(record)


@router.post("/experiments", response_model=ResearchExperimentResponse, status_code=201)
def create_agent_experiment(
    payload: AgentResearchExperimentCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_role(
        db,
        agent,
        capability="experiment-specification",
        package_name="m13-experiment-specification",
    )
    record = register_experiment(
        db,
        ResearchExperimentCreate(**payload.model_dump(), registered_by=agent.slug),
    )
    return ResearchExperimentResponse.model_validate(record)


@router.post(
    "/results/{result_id}/{review_role}",
    response_model=ResearchReviewResponse,
    status_code=201,
)
def create_agent_result_review(
    result_id: UUID,
    review_role: Literal["statistical-review", "adversarial-audit"],
    payload: AgentResearchReviewCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    capability, package_name, review_kind = {
        "statistical-review": (
            "statistical-review",
            "m13-statistical-reviewer",
            "independent_review",
        ),
        "adversarial-audit": (
            "adversarial-audit",
            "m13-adversarial-auditor",
            "adversarial_review",
        ),
    }[review_role]
    _require_role(db, agent, capability=capability, package_name=package_name)
    record = add_review(
        db,
        "result",
        result_id,
        ResearchReviewCreate(
            **payload.model_dump(),
            review_kind=review_kind,
            reviewer=agent.slug,
        ),
    )
    return ResearchReviewResponse.model_validate(record)


@router.post(
    "/trials/{trial_id}/results",
    response_model=ResearchResultResponse,
    status_code=201,
)
def create_agent_result(
    trial_id: UUID,
    payload: AgentResearchResultCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    _require_role(
        db,
        agent,
        capability="research-execution",
        package_name="m13-research-execution",
    )
    record = register_result(
        db,
        trial_id,
        ResearchResultCreate(**payload.model_dump(), recorded_by=agent.slug),
    )
    return ResearchResultResponse.model_validate(record)
