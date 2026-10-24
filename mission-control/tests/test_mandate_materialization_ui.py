from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "hermes_mission_control" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
SCRIPT = (STATIC / "app.js").read_text(encoding="utf-8")


def test_mandate_management_supports_weekly_and_monthly_authority() -> None:
    assert 'id="alpha-mandate-workbench"' in HTML
    assert '<option value="weekly">Weekly · 7 days</option>' in HTML
    assert '<option value="monthly">Monthly · 30 days</option>' in HTML
    assert 'id="mandate-dialog"' in HTML
    assert "expected_source_mandate_digest" in SCRIPT
    assert '"/api/research/alpha-discovery/mandates/renew"' in SCRIPT


def test_founder_hypothesis_binds_authority_only_at_materialization() -> None:
    assert 'id="proposal-mandate-panel"' in HTML
    assert 'name="mandate_id"' in HTML
    assert (
        'proposal.proposal.proposed_task?.task_type === "founder_hypothesis_intake"'
        in SCRIPT
    )
    assert "proposal.proposal.proposed_task?.input_contract" in SCRIPT
    assert "payload.mandate_id = mandate.id" in SCRIPT
    assert "payload.mandate_digest = mandate.mandate_digest" in SCRIPT
    assert (
        "Select or activate a bounded research mandate before materialization."
        in SCRIPT
    )


def test_mandate_activation_exposes_exact_digest_and_boundary() -> None:
    assert 'name="digest_acknowledged"' in HTML
    assert (
        "No capital, orders, shadow admission, code changes, or self-evaluation"
        in SCRIPT
    )
    assert "expected_mandate_digest" in SCRIPT
    assert "openMandateApproval(prepared)" in SCRIPT
