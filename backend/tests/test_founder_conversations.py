from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from app.main import app
from app.schemas import (
    ConversationCreate,
    ConversationTransition,
    ConversationTurnCreate,
    FounderProposalDocument,
)
from app.services.conversations import (
    _bounded_summary,
    _classify_project,
    _specification_guide,
)
from app.services.proposals import create_proposal
from fastapi import HTTPException

AUGUST_23_TRANSCRIPT = [
    "Backtest whether an equity risk-off regime predicts BTC residual returns over one month.",
    "Choose the best options and select a random one month range.",
    "January to February 2022; use a stable universe and choose the best net-EV option.",
    "Do not ask for more clarification. Run the most reasonable test.",
    "Answer all remaining questions yourself and do the test.",
]


def test_conversation_contracts_are_bounded_and_channel_explicit() -> None:
    created = ConversationCreate(
        founder_key="founder:primary",
        channel="telegram",
        title="BTC residual research",
        message=AUGUST_23_TRANSCRIPT[0],
        channel_message_id="100",
    )
    turn = ConversationTurnCreate(
        founder_key=created.founder_key,
        channel="mission-control",
        message=AUGUST_23_TRANSCRIPT[1],
        channel_message_id="101",
        reply_to_channel_message_id="100",
    )
    transition = ConversationTransition(
        founder_key=created.founder_key,
        action="finish",
        reason="Founder marked the job complete.",
    )

    assert created.channel == "telegram"
    assert turn.channel == "mission-control"
    assert turn.reply_to_channel_message_id == "100"
    assert transition.action == "finish"


def test_conversation_workspace_contract_exposes_governed_work_lineage() -> None:
    document = app.openapi()
    route = document["paths"]["/v1/conversations/{conversation_id}/workspace"]
    schema = document["components"]["schemas"]["ConversationWorkspaceResponse"]

    assert set(route) == {"get"}
    assert set(schema["required"]) == {
        "conversation",
        "events",
        "proposals",
        "tasks",
        "approvals",
        "artifacts",
    }


def test_august_23_transcript_retains_research_identity_and_order() -> None:
    assert _classify_project(AUGUST_23_TRANSCRIPT) == "bulletproof_bt"
    summary = _bounded_summary(AUGUST_23_TRANSCRIPT)
    assert summary.index("equity risk-off") < summary.index("January to February 2022")
    assert summary.endswith("Answer all remaining questions yourself and do the test.")


def test_research_specification_generates_ids_and_explains_required_formats() -> None:
    guide = _specification_guide("bulletproof_bt")

    assert {"program_id", "hypothesis_id"} <= set(guide["system_generated"])
    assert guide["reasonable_defaults"]["base_ref"] == "main"
    assert "train_fraction" in guide["formats"]
    assert "hypothesis meaning" in guide["never_default"]


def test_stale_planner_revision_cannot_submit_a_proposal() -> None:
    source = SimpleNamespace(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        task_type="founder_request",
        conversation_id=UUID("22222222-2222-4222-8222-222222222222"),
        conversation_revision=2,
    )
    planner = SimpleNamespace(
        id=UUID("33333333-3333-4333-8333-333333333333"),
        capabilities=["founder-intake"],
    )
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(revision=3)
    document = FounderProposalDocument.model_validate(
        {
            "schema_version": 1,
            "summary": "The stale revision would create a validation task.",
            "interpretation": "The request maps to bounded repository validation.",
            "recommended_action": "decline",
            "assumptions": [],
            "clarification_questions": [],
            "target_role": None,
            "target_role_reason": None,
            "safety_constraints": [],
            "unresolved_fields": [],
            "specification_format": {},
            "resolved_defaults": [],
            "proposed_task": None,
        }
    )

    with pytest.raises(HTTPException, match="newer founder turn") as error:
        create_proposal(db, source_task=source, planner=planner, document=document)

    assert error.value.status_code == 409
