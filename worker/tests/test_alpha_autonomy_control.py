from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "alpha_autonomy_control", ROOT / "scripts" / "alpha_autonomy_control.py"
)
assert SPEC is not None and SPEC.loader is not None
control = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(control)


def test_drain_document_defaults_active_without_global_scope() -> None:
    document = control.drain_document([])
    assert document["paused"] is False
    assert document["mode"] == "active"
    assert document["running_work_allowed_to_finish"] is True


def test_drain_document_projects_audited_global_pause() -> None:
    document = control.drain_document(
        [
            {
                "scope_type": "global",
                "scope_key": "all",
                "is_paused": True,
                "reason": "Local authoring runtime maintenance",
                "updated_at": "2026-10-03T12:00:00Z",
            }
        ]
    )
    assert document["paused"] is True
    assert document["mode"] == "drain"
    assert document["new_control_plane_leases_blocked"] is True
    assert document["new_native_jobs_blocked"] is True


def test_pause_marker_follows_projected_state(tmp_path) -> None:
    marker = tmp_path / "autonomy.paused"
    control.project_pause_marker(marker, paused=True)
    assert marker.is_file()
    assert marker.stat().st_mode & 0o777 == 0o600
    control.project_pause_marker(marker, paused=False)
    assert not marker.exists()
