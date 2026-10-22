from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "src/hermes_mission_control/static/app.js"
HTML = ROOT / "src/hermes_mission_control/static/index.html"
STYLES = ROOT / "src/hermes_mission_control/static/styles.css"


def test_execution_workspace_loads_normalized_event_history_on_demand():
    source = SCRIPT.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")

    assert "request(`/api/execution/events${query}`)" in source
    assert 'view === "execution" && !state.venueEvents' in source
    assert 'id="execution-timeline"' in html
    assert 'id="execution-event-status"' in html
    assert 'id="execution-event-count"' in html


def test_replay_ui_keeps_environment_and_freshness_semantics_distinct():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "Demo evidence only" in source
    assert "No live capital or order authority is implied" in source
    assert "This is an immutable replay, not a live stream" in source
    assert "Mixed environment replay" in source
    assert "Published replay" in source
    assert "legacy_summary_only" in source


def test_event_inspector_traces_lifecycle_and_exact_evidence():
    source = SCRIPT.read_text(encoding="utf-8")

    for required in (
        "correlation_id",
        "client_order_id",
        "venue_order_id",
        "execution_id",
        "exchange_time",
        "observed_time",
        "receipt_digest",
        "projection_digest",
        "event_digest",
        "raw_reference_digest",
        "Related lifecycle",
        "Sanitized canonical payload",
    ):
        assert required in source
    assert "data-related-event" in source
    assert "data-copy-value" in source
    assert "event.evidence?.event_digest || event.event_id" in source
    assert "candidate.account_pseudonym === event.account_pseudonym" in source


def test_exchange_links_are_environment_allowlisted_and_secrets_redacted():
    source = SCRIPT.read_text(encoding="utf-8")

    for host in (
        "testnet.bybit.com",
        "www.bybit.com",
        "testnet.binancefuture.com",
        "www.binance.com",
    ):
        assert host in source
    assert 'url.protocol === "https:"' in source
    assert 'event.environment === "shadow"' in source
    assert 'rel="noopener noreferrer"' in source
    for forbidden in (
        '"api_key"',
        '"secret"',
        '"token"',
        '"password"',
        '"private_key"',
        '"signature"',
        '"raw_payload"',
    ):
        assert forbidden in source
    assert 'normalized.includes("credential")' in source


def test_timeline_is_keyboard_operable_responsive_and_reduced_motion_safe():
    styles = STYLES.read_text(encoding="utf-8")
    source = SCRIPT.read_text(encoding="utf-8")

    assert '<button class="venue-event" type="button"' in source
    assert ".venue-event:focus-visible" in styles
    assert "@media (max-width: 680px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert ".timeline-skeleton span { animation: none; }" in styles
