import json
import math

import pytest

from swarm_worker.scientific_precision import PrecisionDesign, sensitivity_report


def test_null_size_and_requested_power_are_exact_under_approximation():
    d = PrecisionDesign(40, 810, design_effect=2.25)
    assert d.power(0) == pytest.approx(0.0125)
    assert d.power(d.mde_sd()) == pytest.approx(0.8)
    assert d.standard_error_sd == pytest.approx(math.sqrt(2.25 * (1 / 40 + 1 / 810)))
    assert 0.74 < d.mde_sd() < 0.76


def test_directional_sensitivity_and_required_counts():
    d = PrecisionDesign(40, 810)
    assert PrecisionDesign(40, 810, design_effect=4).mde_sd() == pytest.approx(2 * d.mde_sd())
    assert PrecisionDesign(80, 1620).mde_sd() < d.mde_sd()
    assert PrecisionDesign(40, 810, family_size=8).mde_sd() > d.mde_sd()
    counts = d.required_counts(0.1)
    assert PrecisionDesign(counts["events"], counts["controls"]).power(0.1) >= 0.8


def test_reproducible_monte_carlo_and_explicit_claim_boundary():
    kwargs = dict(designs=[PrecisionDesign(40, 810, design_effect=x) for x in [1, 4]],
                  effects=[0, 0.25, 1], replicates=20_000, seed=42)
    report = sensitivity_report(**kwargs)
    assert report == sensitivity_report(**kwargs)
    for cell in report["cells"]:
        assert abs(cell["analytic_power"] - cell["simulated_power"]) <= (
            5 * cell["monte_carlo_standard_error"] + 1 / report["replicates"])
    assert report["market_data_used"] is report["scientific_approval"] is report["execution_authority"] is False
    assert report["report_digest"] != sensitivity_report(**{**kwargs, "seed": 43})["report_digest"]
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("updates", [
    {"event_count": 0}, {"control_count": True}, {"family_size": 0},
    {"design_effect": float("nan")}, {"design_effect": 0.5},
    {"alpha": 1}, {"target_power": 0.01},
])
def test_invalid_design_rejected(updates):
    with pytest.raises(ValueError):
        PrecisionDesign(**({"event_count": 40, "control_count": 810} | updates))


def test_probe_bounds_and_bad_effects():
    d = PrecisionDesign(40, 810)
    for effects in [[float("nan")], [-1], []]:
        with pytest.raises(ValueError):
            sensitivity_report(designs=[d], effects=effects)
    with pytest.raises(ValueError):
        sensitivity_report(designs=[d] * 101, effects=[0])
    with pytest.raises(ValueError):
        sensitivity_report(designs=[d], effects=[0], replicates=1_000_000)
    with pytest.raises(ValueError):
        d.required_counts(1e-100)
