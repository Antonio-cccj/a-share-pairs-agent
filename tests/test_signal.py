"""Tests for the Z-score signal generator."""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.pair_selection import PairCandidate
from strategy.zscore_signal import SignalConfig, generate_signals


def test_signal_opens_on_extreme_z():
    """When the spread is way above mean, we should open a short-spread."""
    n = 200
    rng = np.random.default_rng(0)
    a = pd.Series(
        100 + np.cumsum(rng.normal(0, 1, n)), index=pd.bdate_range("2020-01-01", periods=n)
    )
    b = 5 + 1.0 * a + rng.normal(0, 1, n)
    # Inject a big spread spike near the end.
    b.iloc[-1] += 50.0

    prices = pd.concat(
        [
            pd.DataFrame({"ts_code": "A", "trade_date": a.index, "close": a.values}),
            pd.DataFrame({"ts_code": "B", "trade_date": b.index, "close": b.values}),
        ],
        ignore_index=True,
    )
    prices["trade_date"] = prices["trade_date"].dt.date

    pair = PairCandidate(
        code_a="A",
        code_b="B",
        industry="X",
        pvalue=0.001,
        hedge_ratio=1.0,
        intercept=5.0,
        half_life=10.0,
        adf_stat=-3.5,
    )
    out = generate_signals(prices, pair, cfg=SignalConfig(open_z=2.0, close_z=0.5))

    assert not out.empty
    # At least one trade should fire across the path.
    assert (out["pos"].diff().abs() > 0).any()
