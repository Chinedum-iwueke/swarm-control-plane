from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.agents import router as agents_router
from app.api.routes.controls import router as controls_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.task_runtime import router as task_runtime_router
from app.api.routes.tasks import router as tasks_router

__all__ = [
    "agent_runtime_router",
    "agents_router",
    "controls_router",
    "health_router",
    "metrics_router",
    "task_runtime_router",
    "tasks_router",
]
