from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src" / "hermes_mission_control" / "static" / "app.js"
STYLES = ROOT / "src" / "hermes_mission_control" / "static" / "styles.css"


def test_backtest_cards_count_only_native_terminal_receipts_as_complete():
    source = APP_JS.read_text(encoding="utf-8")
    assert 'item.execution_evidence === "native_terminal_receipt"' in source
    assert "item.terminal_receipt?.present" in source
    assert "terminal task is retained for diagnosis" in source
    assert "completed · ${page.total || 0} execution records" in source


def test_backtest_inspector_exposes_full_scientific_evidence_contract():
    source = APP_JS.read_text(encoding="utf-8")
    for label in (
        "Hypothesis and specification",
        "Dataset, universe and representation",
        "Strategy, search and execution",
        "Evaluation gates",
        "Terminal receipt",
        "Exact reports and artifacts",
    ):
        assert label in source
    assert 'value === "not_run"' in source
    assert "data-backtest-open" in source
    assert "data-artifact-id" in source
    assert "data-task-id" in source


def test_backtest_cards_have_distinct_receipt_and_gate_states():
    styles = STYLES.read_text(encoding="utf-8")
    assert ".backtest-card.receipt-complete" in styles
    assert ".backtest-card.receipt-missing" in styles
    assert ".backtest-gate-summary .gate-unrun" in styles
    assert ".backtest-gate-grid" in styles
