"""Run with Bulletproof's Python and PYTHONPATH=src in the checkout under test.

These offline probes supplement, rather than replace, its frozen native tests.
"""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "retained_card_tests", Path.cwd() / "tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py"
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_empirical_threshold_equality_is_included():
    strategy = M.Btc5mImpactProxyReversalStrategy(
        impact_proxy_threshold=0.99, normalization_window=288
    )
    # Exact binary ratios avoid approximate-equality and float-rounding excuses.
    signals = M._run_returns(strategy, [1.0, -0.5] * 160)
    assert signals, "Frozen evaluator includes empirical threshold ties; native must too"
    assert all(s.metadata["impact_proxy"] == s.metadata["impact_proxy_threshold_value"] for s in signals)


def test_stop_uses_twenty_completed_buckets_including_decision_bucket():
    strategy = M.Btc5mImpactProxyReversalStrategy(
        impact_proxy_threshold=0.99, normalization_window=288
    )
    returns = [0.001] * 300 + [0.1]
    signals = M._run_returns(strategy, returns)
    assert signals
    close = 100.0
    ranges = []
    for change in returns:
        previous = close
        close *= 1.0 + change
        ranges.append(max(2.0, abs(close + 1.0 - previous), abs(close - 1.0 - previous)))
    expected_stop = close + 3.0 * sum(ranges[-20:]) / 20
    assert signals[-1].metadata["stop_price"] == pytest.approx(expected_stop)
