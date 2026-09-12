from app.api.routes.agent_context import agent_router as agent_context_runtime_router
from app.api.routes.agent_context import router as agent_context_router
from app.api.routes.agent_governance import router as agent_governance_router
from app.api.routes.agent_research import router as agent_research_router
from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.agents import router as agents_router
from app.api.routes.alpha_campaign import router as alpha_campaign_router
from app.api.routes.authority import router as authority_router
from app.api.routes.autonomous_research import router as autonomous_research_router
from app.api.routes.calibrations import router as calibrations_router
from app.api.routes.candidate_admission_schemas import (
    router as candidate_admission_schemas_router,
)
from app.api.routes.causal_pipelines import router as causal_pipelines_router
from app.api.routes.controls import router as controls_router
from app.api.routes.conversations import channel_router as channel_conversations_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.corpus import router as corpus_router
from app.api.routes.corpus_sync import router as corpus_sync_router
from app.api.routes.curriculum import router as curriculum_router
from app.api.routes.data_contracts import router as data_contracts_router
from app.api.routes.derived_state import router as derived_state_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.discovery_portfolio import router as discovery_portfolio_router
from app.api.routes.evaluator_routing import router as evaluator_routing_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.execution_calibration_schemas import (
    router as execution_calibration_schemas_router,
)
from app.api.routes.execution_event_schemas import (
    router as execution_event_schemas_router,
)
from app.api.routes.factor_language import router as factor_language_router
from app.api.routes.falsification import router as falsification_router
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
from app.api.routes.intelligence_evaluation import (
    router as intelligence_evaluation_router,
)
from app.api.routes.laboratory import router as laboratory_router
from app.api.routes.lake_operations import router as lake_operations_router
from app.api.routes.lifecycle import router as lifecycle_router
from app.api.routes.lifecycle_consequence import router as lifecycle_consequence_router
from app.api.routes.market_data_catalog import router as market_data_catalog_router
from app.api.routes.memory import router as memory_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.microstructure_models import router as microstructure_models_router
from app.api.routes.missions import router as missions_router
from app.api.routes.model_evaluations import router as model_evaluations_router
from app.api.routes.observability import router as observability_router
from app.api.routes.off_policy import router as off_policy_router
from app.api.routes.offline_rl import router as offline_rl_router
from app.api.routes.oms_schemas import router as oms_schemas_router
from app.api.routes.operational_notes import agent_router as agent_notes_router
from app.api.routes.operational_notes import router as operational_notes_router
from app.api.routes.operations import router as operations_router
from app.api.routes.packages import agent_router as agent_packages_router
from app.api.routes.packages import router as packages_router
from app.api.routes.platform import router as platform_router
from app.api.routes.portfolio_capacity_schemas import (
    router as portfolio_capacity_schemas_router,
)
from app.api.routes.portfolio_solvers import router as portfolio_solvers_router
from app.api.routes.prompt_policies import router as prompt_policies_router
from app.api.routes.proposals import agent_router as agent_proposals_router
from app.api.routes.proposals import router as proposals_router
from app.api.routes.quantitative_receipts import router as quantitative_receipts_router
from app.api.routes.realtime_risk_schemas import router as realtime_risk_schemas_router
from app.api.routes.reference_data import router as reference_data_router
from app.api.routes.research import router as research_router
from app.api.routes.research_bridge import router as research_bridge_router
from app.api.routes.research_programs import router as research_programs_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.risk_budget_schemas import router as risk_budget_schemas_router
from app.api.routes.risk_rules import router as risk_rules_router
from app.api.routes.risk_stress import router as risk_stress_router
from app.api.routes.runbook_packages import router as runbook_packages_router
from app.api.routes.scientific_fidelity import router as scientific_fidelity_router
from app.api.routes.selection_audit import router as selection_audit_router
from app.api.routes.shadow_monitoring_schemas import (
    router as shadow_monitoring_schemas_router,
)
from app.api.routes.statistical_search import router as statistical_search_router
from app.api.routes.supervisor import router as supervisor_router
from app.api.routes.surveillance import router as surveillance_router
from app.api.routes.symbolic_search import router as symbolic_search_router
from app.api.routes.task_graphs import router as task_graphs_router
from app.api.routes.task_runtime import router as task_runtime_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.venue_identities import router as venue_identities_router
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
    "alpha_campaign_router",
    "authority_router",
    "autonomous_research_router",
    "calibrations_router",
    "candidate_admission_schemas_router",
    "causal_pipelines_router",
    "channel_conversations_router",
    "controls_router",
    "conversations_router",
    "corpus_router",
    "corpus_sync_router",
    "curriculum_router",
    "data_contracts_router",
    "derived_state_router",
    "discovery_portfolio_router",
    "discovery_router",
    "evaluator_routing_router",
    "evidence_router",
    "execution_calibration_schemas_router",
    "execution_event_schemas_router",
    "factor_language_router",
    "falsification_router",
    "fleet_router",
    "founder_channel_router",
    "governance_audit_router",
    "governance_router",
    "graph_router",
    "health_router",
    "ingestion_recovery_router",
    "ingestion_router",
    "institutional_lifecycle_router",
    "intelligence_evaluation_router",
    "laboratory_router",
    "lake_operations_router",
    "lifecycle_consequence_router",
    "lifecycle_router",
    "market_data_catalog_router",
    "memory_router",
    "metrics_router",
    "microstructure_models_router",
    "missions_router",
    "model_evaluations_router",
    "observability_router",
    "off_policy_router",
    "offline_rl_router",
    "oms_schemas_router",
    "operational_notes_router",
    "operations_router",
    "packages_router",
    "platform_router",
    "portfolio_capacity_schemas_router",
    "portfolio_solvers_router",
    "prompt_policies_router",
    "proposals_router",
    "quantitative_receipts_router",
    "realtime_risk_schemas_router",
    "reference_data_router",
    "research_bridge_router",
    "research_programs_router",
    "research_router",
    "retrieval_router",
    "risk_budget_schemas_router",
    "risk_rules_router",
    "risk_stress_router",
    "runbook_packages_router",
    "scientific_fidelity_router",
    "selection_audit_router",
    "shadow_monitoring_schemas_router",
    "statistical_search_router",
    "supervisor_router",
    "surveillance_router",
    "symbolic_search_router",
    "task_graphs_router",
    "task_runtime_router",
    "tasks_router",
    "venue_identities_router",
    "workload_identities_router",
]
