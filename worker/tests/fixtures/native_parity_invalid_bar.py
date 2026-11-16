"""Counterexample probe; run separately against baseline and reconstructed sources."""
import importlib.util
import math
from pathlib import Path

import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "retained_card_tests", Path.cwd() / "tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py"
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_file_loader_rejects_nan_before_strategy(tmp_path):
    from bt.data.loader import load_bars

    frame = pd.DataFrame({"ts": [pd.Timestamp("2024-01-01", tz="UTC")],
        "symbol": ["BTCUSDT"], "open": [100.0], "high": [float("nan")],
        "low": [99.0], "close": [100.0], "volume": [1.0]})
    path = tmp_path / "invalid.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="Required columns must not contain NaNs"):
        load_bars(path)


def test_closed_positions_are_removed_from_engine_position_book():
    from bt.core.enums import Side
    from bt.core.types import Fill
    from bt.portfolio.position import PositionBook

    book = PositionBook()
    start = pd.Timestamp("2024-01-01", tz="UTC")
    book.apply_fill(Fill("entry", start, "BTCUSDT", Side.BUY, 1.0, 100.0, 0.0, 0.0))
    assert "BTCUSDT" in book.all_positions()
    book.apply_fill(Fill("exit", start + pd.Timedelta(minutes=1), "BTCUSDT", Side.SELL, 1.0, 101.0, 0.0, 0.0))
    assert "BTCUSDT" not in book.all_positions()


def test_nonfinite_high_must_not_poison_atr_state():
    strategy = M.Btc5mImpactProxyReversalStrategy()
    M._run_returns(strategy, [0.001] * 300)
    start = pd.Timestamp("2023-01-01T00:00:00Z") + pd.Timedelta(minutes=1500)
    for minute in range(5):
        ts = start + pd.Timedelta(minutes=minute)
        bar = M.Bar(ts, "BTCUSDT", 100.0, float("nan"), 99.0, 100.0, 1.0,
                    {"quote_volume": 400_000.0})
        strategy.on_bars(ts, {"BTCUSDT": bar}, {"BTCUSDT"}, {"positions": {}, "htf": {"5m": {}}})
    assert all(math.isfinite(value) for value in strategy._ranges.get("BTCUSDT", [])), (
        "Nonfinite OHLC contaminated retained ATR state"
    )
