"""Cost-model unit tests."""

from __future__ import annotations

import pandas as pd

from backtest.costs import CostModel


def test_buy_cost_only_commission_and_slippage():
    cm = CostModel(commission_bps=3, stamp_duty_bps=10, slippage_bps=5)
    # Pure buy: notional increases by 1000.
    delta = pd.Series([1000.0])
    cost = cm.cost_per_turnover(delta).iloc[0]
    # 3 bps + 5 bps = 8 bps on 1000 = 0.8 (no stamp on buy).
    assert abs(cost - 0.8) < 1e-9


def test_sell_includes_stamp_duty():
    cm = CostModel(commission_bps=3, stamp_duty_bps=10, slippage_bps=5)
    delta = pd.Series([-1000.0])
    cost = cm.cost_per_turnover(delta).iloc[0]
    # 3 + 5 + 10 = 18 bps -> 1.8 on 1000.
    assert abs(cost - 1.8) < 1e-9


def test_round_trip_helper_matches_components():
    cm = CostModel(commission_bps=3, stamp_duty_bps=10, slippage_bps=5)
    assert cm.total_cost_bps("round_trip") == 2 * 3 + 2 * 5 + 10
