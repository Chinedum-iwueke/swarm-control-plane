import pytest
from pydantic import ValidationError

from app.schemas.alpha_discovery import AlphaCoverageReplanningPolicy
from app.services.alpha_coverage_policy import discovery_panels, coverage_window


def test_historical_envelope_is_explicit_and_bounded():
    values = dict(
        envelope_start="2023-08-08T00:00:00Z", envelope_end="2026-08-07T00:00:00Z"
    )
    policy = AlphaCoverageReplanningPolicy(**values)
    assert policy.maximum_successors == 2
    assert policy.outcome_search_allowed is False
    for invalid in (
        {"maximum_successors": 100},
        {"maximum_successors": True},
        {"outcome_search_allowed": True},
        {"envelope_start": "2020-01-01T00:00:00Z"},
        {"envelope_end": "2023-09-01"},
    ):
        with pytest.raises(ValidationError):
            AlphaCoverageReplanningPolicy(**(values | invalid))


def test_old_mandates_do_not_silently_gain_historical_authority():
    spec = {
        "execution_window_start": "2025-01-01T00:00:00Z",
        "execution_window_end": "2026-01-01T00:00:00Z",
    }
    assert coverage_window(spec)["start"] == spec["execution_window_start"]
    spec["historical_window_policy"] = {
        "coverage_replanning": {
            "envelope_start": "2023-01-02T00:00:00Z",
            "envelope_end": spec["execution_window_end"],
        }
    }
    assert coverage_window(spec)["start"] == "2023-01-02T00:00:00Z"


def test_registered_panels_are_visible_despite_short_history_and_gaps():
    panel = {
        "exchange": "bybit",
        "symbol": "TRBUSDT",
        "dataset": "ohlcv",
        "timeframe": "1m",
        "actual_rows": 300,
        "missing_rows": 5,
    }
    catalog = {
        "availability": [
            panel,
            panel | {"dataset": "funding"},
            panel | {"actual_rows": 0},
        ]
    }
    assert [x["instrument"] for x in discovery_panels(catalog)] == ["TRBUSDT"]
    assert discovery_panels({"one_year_coverage_candidates": [panel]}) == [panel]
