from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.main import app
from app.services import derived_state as service
from app.services.derived_state import _next_version, select_strategy
from fastapi import HTTPException


def test_strategy_uses_delta_only_for_complete_bounded_change_ledger() -> None:
    assert (
        select_strategy(
            force_full=False,
            ledger_epochs=[42, 43],
            source_epoch_start=41,
            source_epoch_target=43,
            projection_states_exist=True,
            changed_object_count=12,
        )
        == "incremental"
    )
    assert (
        select_strategy(
            force_full=False,
            ledger_epochs=[44],
            source_epoch_start=41,
            source_epoch_target=44,
            projection_states_exist=True,
            changed_object_count=1,
        )
        == "full"
    )
    assert (
        select_strategy(
            force_full=True,
            ledger_epochs=[42],
            source_epoch_start=41,
            source_epoch_target=42,
            projection_states_exist=True,
            changed_object_count=1,
        )
        == "full"
    )


def test_strategy_falls_back_for_first_build_and_oversized_delta() -> None:
    assert (
        select_strategy(
            force_full=False,
            ledger_epochs=[1],
            source_epoch_start=0,
            source_epoch_target=1,
            projection_states_exist=False,
            changed_object_count=1,
        )
        == "full"
    )
    assert (
        select_strategy(
            force_full=False,
            ledger_epochs=[42],
            source_epoch_start=41,
            source_epoch_target=42,
            projection_states_exist=True,
            changed_object_count=5_001,
        )
        == "full"
    )


def test_semantic_version_increment_is_deterministic() -> None:
    assert _next_version(["1.0.0", "1.0.2", "1.0.1"]) == "1.0.3"
    assert _next_version([]) == "1.0.0"


def test_phase_fails_closed_if_corpus_moves(monkeypatch) -> None:
    monkeypatch.setattr(service, "freshness_snapshot", lambda _db: ("a" * 64, 43))
    run = SimpleNamespace(source_epoch_target=42)
    with pytest.raises(HTTPException, match="changed during"):
        service._execute_phase(MagicMock(), run, "retrieval")


def test_forced_full_rebuild_does_not_reuse_current_state(monkeypatch) -> None:
    state = SimpleNamespace(
        projection_name="canonical-scientific",
        projection_version="hybrid-retrieval-v1.1.0",
        corpus_digest="a" * 64,
        source_epoch=42,
        object_count=3,
    )
    db = MagicMock()
    db.get.return_value = state
    build = MagicMock(return_value=state)
    monkeypatch.setattr(service, "freshness_snapshot", lambda _db: ("a" * 64, 42))
    monkeypatch.setattr(service, "build_projections", build)

    result = service._execute_phase(
        db,
        SimpleNamespace(id=uuid4(), source_epoch_target=42, strategy="full"),
        "retrieval",
    )

    build.assert_called_once()
    assert build.call_args.args == (db,)
    assert callable(build.call_args.kwargs["progress"])
    assert result["strategy"] == "full"


def test_fresh_running_reconciliation_is_not_executed_twice() -> None:
    run = SimpleNamespace(id=uuid4(), state="running", heartbeat_at=datetime.now(UTC))
    db = MagicMock()
    db.get.return_value = run

    assert service.execute_reconciliation(db, run.id) is run
    db.commit.assert_not_called()


def test_derived_state_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/v1/research/derived-state/status" in paths
    assert "/v1/research/derived-state/reconciliations" in paths
    assert "/v1/research/derived-state/reconciliations/{run_id}/execute" in paths


def test_migration_records_object_edge_alias_and_provenance_changes() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/d2e8f5b13a70_add_incremental_derived_state.py"
    ).read_text(encoding="utf-8")
    assert "record_derived_state_change" in migration
    assert "canonical_evidence_objects" in migration
    assert "canonical_evidence_edges" in migration
    assert "canonical_identity_aliases" in migration
    assert "row_value.provenance_object_id" in migration
    assert "txid_current()" in migration
