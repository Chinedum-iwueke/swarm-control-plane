from fastapi import FastAPI

from app.api.routes import (
    agent_notes_router,
    agent_packages_router,
    agent_proposals_router,
    agent_research_router,
    agent_runtime_router,
    agents_router,
    controls_router,
    corpus_router,
    data_contracts_router,
    evidence_router,
    founder_channel_router,
    governance_router,
    health_router,
    ingestion_router,
    memory_router,
    metrics_router,
    missions_router,
    operational_notes_router,
    packages_router,
    proposals_router,
    research_programs_router,
    research_router,
    retrieval_router,
    runbook_packages_router,
    supervisor_router,
    surveillance_router,
    task_runtime_router,
    tasks_router,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(health_router)
app.include_router(corpus_router)
app.include_router(ingestion_router)
app.include_router(metrics_router)
app.include_router(memory_router)
app.include_router(missions_router)
app.include_router(operational_notes_router)
app.include_router(packages_router)
app.include_router(agent_packages_router)
app.include_router(agent_proposals_router)
app.include_router(agents_router)
app.include_router(controls_router)
app.include_router(data_contracts_router)
app.include_router(evidence_router)
app.include_router(founder_channel_router)
app.include_router(governance_router)
app.include_router(agent_runtime_router)
app.include_router(agent_research_router)
app.include_router(agent_notes_router)
app.include_router(tasks_router)
app.include_router(proposals_router)
app.include_router(research_router)
app.include_router(retrieval_router)
app.include_router(research_programs_router)
app.include_router(runbook_packages_router)
app.include_router(task_runtime_router)
app.include_router(supervisor_router)
app.include_router(surveillance_router)
