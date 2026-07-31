from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.agents import router as agents_router
from app.api.routes.controls import router as controls_router
from app.api.routes.founder_channel import router as founder_channel_router
from app.api.routes.governance import router as governance_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.missions import router as missions_router
from app.api.routes.packages import agent_router as agent_packages_router
from app.api.routes.packages import router as packages_router
from app.api.routes.proposals import agent_router as agent_proposals_router
from app.api.routes.proposals import router as proposals_router
from app.api.routes.runbook_packages import router as runbook_packages_router
from app.api.routes.supervisor import router as supervisor_router
from app.api.routes.task_runtime import router as task_runtime_router
from app.api.routes.tasks import router as tasks_router

__all__ = [
    "agent_packages_router",
    "agent_proposals_router",
    "agent_runtime_router",
    "agents_router",
    "controls_router",
    "founder_channel_router",
    "governance_router",
    "health_router",
    "metrics_router",
    "missions_router",
    "packages_router",
    "proposals_router",
    "runbook_packages_router",
    "supervisor_router",
    "task_runtime_router",
    "tasks_router",
]
