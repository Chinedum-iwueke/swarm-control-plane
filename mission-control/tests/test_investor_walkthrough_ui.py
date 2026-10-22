from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "src/hermes_mission_control/static/app.js"
HTML = ROOT / "src/hermes_mission_control/static/index.html"
STYLES = ROOT / "src/hermes_mission_control/static/styles.css"


def test_command_exposes_bounded_investor_walkthrough():
    html = HTML.read_text(encoding="utf-8")

    assert 'id="open-investor-walkthrough"' in html
    assert 'id="walkthrough-coach"' in html
    assert 'aria-label="Investor walkthrough"' in html
    assert 'id="walkthrough-finding-dialog"' in html


def test_walkthrough_uses_canonical_projection_and_retains_observations():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'request("/api/investor-walkthrough?refresh=true")' in source
    assert 'get("walkthrough") === "1"' in source
    assert "await openInvestorWalkthrough()" in source
    assert 'request("/api/investor-walkthrough/sessions"' in source
    assert "/observations`" in source
    assert "/finish`" in source
    for kind in ("opened", "completed", "question", "misunderstanding", "evidence_gap"):
        assert kind in source or kind in HTML.read_text(encoding="utf-8")


def test_walkthrough_routes_each_ready_step_to_existing_evidence_inspector():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'step.id === "command"' in source
    assert "openWorkflow(step.entity_id)" in source
    assert "await openAgent(step.entity_id)" in source
    assert "openBacktest(step.entity_id)" in source
    assert "openVenueEvent(step.entity_id)" in source


def test_demo_mode_and_unavailable_steps_are_truthfully_disclosed():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'status: "demonstration_only"' in source
    assert "cannot be used as investor rehearsal evidence" in source
    assert "Missing steps will be disclosed, never simulated." in source
    assert "Canonical step unavailable" in source
    assert 'unavailable ? "disabled"' in source


def test_walkthrough_coach_is_responsive_focusable_and_reduced_motion_safe():
    styles = STYLES.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")

    assert ".walkthrough-coach" in styles
    assert "min-height: 44px" in styles
    assert "@media (max-width: 680px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert ".walkthrough-progress span { transition: none; }" in styles
    assert 'aria-live="polite"' in html
