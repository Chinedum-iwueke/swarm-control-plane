from fastapi import FastAPI

from app.api.routes import (
    agent_packages_router,
    agent_proposals_router,
    agent_runtime_router,
    agents_router,
    controls_router,
    founder_channel_router,
    governance_router,
    health_router,
    metrics_router,
    missions_router,
    packages_router,
    proposals_router,
    supervisor_router,
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
app.include_router(metrics_router)
app.include_router(missions_router)
app.include_router(packages_router)
app.include_router(agent_packages_router)
app.include_router(agent_proposals_router)
app.include_router(agents_router)
app.include_router(controls_router)
app.include_router(founder_channel_router)
app.include_router(governance_router)
app.include_router(agent_runtime_router)
app.include_router(tasks_router)
app.include_router(proposals_router)
app.include_router(task_runtime_router)
app.include_router(supervisor_router)
