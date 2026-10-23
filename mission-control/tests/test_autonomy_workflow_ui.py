from pathlib import Path


ROOT = Path(__file__).parents[1]
STATIC = ROOT / "src/hermes_mission_control/static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
SCRIPT = (STATIC / "app.js").read_text(encoding="utf-8")
STYLES = (STATIC / "styles.css").read_text(encoding="utf-8")


def test_autonomy_control_is_in_command_hero_immediately_after_fleet() -> None:
    machine_strip = HTML.index('id="machine-strip"')
    autonomy_hero = HTML.index('id="autonomy-hero"')
    command_grid = HTML.index('class="command-grid"')

    assert machine_strip < autonomy_hero < command_grid
    assert 'data-navigate="autonomy"' in HTML
    assert 'id="autonomy-hero-control"' in HTML


def test_autonomy_workspace_exposes_complete_live_research_loop() -> None:
    assert 'id="autonomy" class="view"' in HTML
    assert 'id="autonomy-canvas"' in HTML
    assert 'id="autonomy-inspector"' in HTML
    assert 'id="autonomy-agents"' in HTML
    assert '"autonomy"' in SCRIPT.splitlines()[0]
    for stage in ("discover", "synthesize", "represent", "specify", "review", "execute", "retain", "admit"):
        assert f'id: "{stage}"' in SCRIPT
    assert "Every terminal result updates novelty, failure memory" in SCRIPT


def test_autonomy_visualization_uses_canonical_state_and_honest_empty_states() -> None:
    assert "state.workflows?.items" in SCRIPT
    assert "state.dashboard.alpha_discovery" in SCRIPT
    assert "state.dashboard.alpha_campaigns" in SCRIPT
    assert "No canonical workflow record is currently bound to this stage." in SCRIPT
    assert "No registered agent role currently matches this stage." in SCRIPT
    assert "native_backtest?.state === \"running\"" in SCRIPT


def test_agent_profiles_use_role_aware_bot_identity_marks() -> None:
    assert "function agentBot(" in SCRIPT
    for kind in ("researcher", "data", "engineer", "reviewer", "executor", "operator"):
        assert f'"{kind}"' in SCRIPT
        assert f".agent-bot.bot-{kind}" in STYLES
    assert '${agentBot(agent, "large")}' in SCRIPT
    assert '${agentBot(detail.agent, "large")}' in SCRIPT


def test_live_motion_is_stateful_and_reduced_motion_safe() -> None:
    assert ".autonomy-connector.is-live i" in STYLES
    assert "@keyframes autonomy-signal" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    assert ".autonomy-hero .autonomy-orbit i, .autonomy-connector.is-live i { animation: none; }" in STYLES

