from app.api.routes.agent_context import agent_router as agent_context_runtime_router
from app.api.routes.agent_context import router as agent_context_router
from app.api.routes.agent_governance import router as agent_governance_router
from app.api.routes.agent_research import router as agent_research_router
from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.agents import router as agents_router
from app.api.routes.authority import router as authority_router
from app.api.routes.controls import router as controls_router
from app.api.routes.conversations import channel_router as channel_conversations_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.corpus import router as corpus_router
from app.api.routes.corpus_sync import router as corpus_sync_router
from app.api.routes.curriculum import router as curriculum_router
from app.api.routes.data_contracts import router as data_contracts_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.fleet import agent_router as agent_fleet_router
from app.api.routes.fleet import router as fleet_router
from app.api.routes.founder_channel import router as founder_channel_router
from app.api.routes.governance import router as governance_router
from app.api.routes.governance_audit import router as governance_audit_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.ingestion_recovery import router as ingestion_recovery_router
from app.api.routes.institutional_lifecycle import (
    router as institutional_lifecycle_router,
)
from app.api.routes.laboratory import router as laboratory_router
from app.api.routes.lifecycle import router as lifecycle_router
from app.api.routes.lifecycle_consequence import router as lifecycle_consequence_router
from app.api.routes.memory import router as memory_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.missions import router as missions_router
from app.api.routes.observability import router as observability_router
from app.api.routes.operational_notes import agent_router as agent_notes_router
from app.api.routes.operational_notes import router as operational_notes_router
from app.api.routes.operations import router as operations_router
from app.api.routes.packages import agent_router as agent_packages_router
from app.api.routes.packages import router as packages_router
from app.api.routes.platform import router as platform_router
from app.api.routes.proposals import agent_router as agent_proposals_router
from app.api.routes.proposals import router as proposals_router
from app.api.routes.research import router as research_router
from app.api.routes.research_bridge import router as research_bridge_router
from app.api.routes.research_programs import router as research_programs_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.runbook_packages import router as runbook_packages_router
from app.api.routes.supervisor import router as supervisor_router
from app.api.routes.surveillance import router as surveillance_router
from app.api.routes.task_graphs import router as task_graphs_router
from app.api.routes.task_runtime import router as task_runtime_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.workload_identities import router as workload_identities_router

__all__ = [
    "agent_context_router",
    "agent_context_runtime_router",
    "agent_fleet_router",
    "agent_governance_router",
    "agent_notes_router",
    "agent_packages_router",
    "agent_proposals_router",
    "agent_research_router",
    "agent_runtime_router",
    "agents_router",
    "authority_router",
    "channel_conversations_router",
    "controls_router",
    "conversations_router",
    "corpus_router",
    "corpus_sync_router",
    "curriculum_router",
    "data_contracts_router",
    "evidence_router",
    "fleet_router",
    "founder_channel_router",
    "governance_audit_router",
    "governance_router",
    "graph_router",
    "health_router",
    "ingestion_recovery_router",
    "ingestion_router",
    "institutional_lifecycle_router",
    "laboratory_router",
    "lifecycle_consequence_router",
    "lifecycle_router",
    "memory_router",
    "metrics_router",
    "missions_router",
    "observability_router",
    "operational_notes_router",
    "operations_router",
    "packages_router",
    "platform_router",
    "proposals_router",
    "research_bridge_router",
    "research_programs_router",
    "research_router",
    "retrieval_router",
    "runbook_packages_router",
    "supervisor_router",
    "surveillance_router",
    "task_graphs_router",
    "task_runtime_router",
    "tasks_router",
    "workload_identities_router",
]
