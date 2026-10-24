from pathlib import Path

STATIC = Path(__file__).parents[1] / "src/hermes_mission_control/static"


def test_critical_workbench_has_keyboard_and_screen_reader_contracts() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert '<a class="skip-link" href="#main-content">' in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert 'id="conversation-live-status"' in html
    assert 'role="status" aria-live="polite" aria-atomic="true"' in html
    assert 'role="tablist" aria-label="Thread state"' in html
    assert 'role="tablist" aria-label="Approval states"' in html
    assert ":focus-visible" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (max-width: 680px)" in css


def test_reconnect_deduplicates_and_scroll_requires_user_reveal() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "conversationEventIds.has(item.id)" in script
    assert "page.next_cursor || state.conversationEventCursor" in script
    assert "conversationPendingUpdates += unseen.length" in script
    marker = "if (revealLatest) progress.lastElementChild?.scrollIntoView"
    assert marker in script
    assert "progress.lastElementChild?.scrollIntoView" not in script.split(marker, 1)[0]


def test_static_asset_performance_budgets() -> None:
    # MCUX-022 owner: Mission Control. These caps prevent silent growth while the
    # current no-bundler deployment remains deliberately self-contained.
    budgets = {"app.js": 340_000, "styles.css": 125_000, "index.html": 60_000}
    for name, limit in budgets.items():
        assert (STATIC / name).stat().st_size <= limit, f"{name} exceeds {limit} bytes"


def test_no_service_worker_can_serve_stale_authority_state() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "serviceWorker.register" not in script
