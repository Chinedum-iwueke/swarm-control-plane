from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src" / "hermes_mission_control" / "static" / "app.js"
STYLES = ROOT / "src" / "hermes_mission_control" / "static" / "styles.css"


def test_agent_inspector_uses_detail_projection_and_all_required_tabs():
    source = APP_JS.read_text(encoding="utf-8")
    assert "/api/agents/${encodeURIComponent(id)}/detail?offset=0&limit=25" in source
    assert '["overview", "now", "history", "workflows", "governance"]' in source
    assert 'role="tablist"' in source
    assert 'role="tabpanel"' in source
    assert 'event.key === "ArrowRight"' in source
    assert 'event.key === "ArrowLeft"' in source


def test_agent_inspector_discloses_provenance_and_does_not_infer_hierarchy():
    source = APP_JS.read_text(encoding="utf-8")
    assert "source.source_identity" in source
    assert "source.freshness_threshold_seconds" in source
    assert "Mission Control does not infer an organization chart" in source
    assert "loadMoreAgentHistory" in source
    assert "data-task-id" in source
    assert "data-artifact-id" in source
    assert "data-workflow-id" in source


def test_agent_inspector_has_focus_loading_and_mobile_layout_rules():
    styles = STYLES.read_text(encoding="utf-8")
    assert '.agent-inspector-tabs button[aria-selected="true"]' in styles
    assert ".agent-inspector-tabs button:focus-visible" in styles
    assert ".agent-detail-loading" in styles
    assert ".source-evidence" in styles
