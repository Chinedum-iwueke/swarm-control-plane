from app.api.routes.agent_research import router as agent_research_router
from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.agents import router as agents_router
from app.api.routes.controls import router as controls_router
from app.api.routes.corpus import router as corpus_router
from app.api.routes.corpus_sync import router as corpus_sync_router
from app.api.routes.data_contracts import router as data_contracts_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.founder_channel import router as founder_channel_router
from app.api.routes.governance import router as governance_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.ingestion_recovery import router as ingestion_recovery_router
from app.api.routes.memory import router as memory_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.missions import router as missions_router
from app.api.routes.operational_notes import agent_router as agent_notes_router
from app.api.routes.operational_notes import router as operational_notes_router
from app.api.routes.packages import agent_router as agent_packages_router
from app.api.routes.packages import router as packages_router
from app.api.routes.proposals import agent_router as agent_proposals_router
from app.api.routes.proposals import router as proposals_router
from app.api.routes.research import router as research_router
from app.api.routes.research_programs import router as research_programs_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.runbook_packages import router as runbook_packages_router
from app.api.routes.supervisor import router as supervisor_router
from app.api.routes.surveillance import router as surveillance_router
from app.api.routes.task_runtime import router as task_runtime_router
from app.api.routes.tasks import router as tasks_router

__all__ = [
    "agent_notes_router",
    "agent_packages_router",
    "agent_proposals_router",
    "agent_research_router",
    "agent_runtime_router",
    "agents_router",
    "controls_router",
    "corpus_router",
    "corpus_sync_router",
    "data_contracts_router",
    "evidence_router",
    "founder_channel_router",
    "governance_router",
    "graph_router",
    "health_router",
    "ingestion_recovery_router",
    "ingestion_router",
    "memory_router",
    "metrics_router",
    "missions_router",
    "operational_notes_router",
    "packages_router",
    "proposals_router",
    "research_programs_router",
    "research_router",
    "retrieval_router",
    "runbook_packages_router",
    "supervisor_router",
    "surveillance_router",
    "task_runtime_router",
    "tasks_router",
]
