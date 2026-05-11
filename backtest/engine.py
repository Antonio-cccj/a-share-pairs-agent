"""Vectorised daily pair-trading backtest engine.

Pipeline per pair
-----------------
1. ``zscore_signal.generate_signals`` -> position series in {-1, 0, +1}.
2. (Optional) ``EventRiskOverlay.apply`` -> throttle by events.
3. ``dollar_neutral.build_positions`` -> per-leg signed CNY weights.
4. Compute leg returns from forward 1-day price changes.
5. Subtract costs via :class:`CostModel`.
6. Aggregate equally across active pairs to obtain portfolio NAV.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from backtest.costs import CostModel
from backtest.metrics import PerformanceMetrics, compute_metrics
from backtest.risk_overlay import EventRiskOverlay
from core.logger import get_logger
from strategy.dollar_neutral import build_positions
from strategy.pair_selection import PairCandidate
from strategy.zscore_signal import SignalConfig, generate_signals

log = get_logger(__name__)


@dataclass
class BacktestResult:
    equity: pd.Series          # portfolio NAV starting at 1.0
    returns: pd.Series         # daily fractional returns
    positions: pd.DataFrame    # tall: ['pair_id', 'date', 'pos', 'w_a', 'w_b']
    pair_pnl: pd.DataFrame     # wide: per-pair daily PnL
    metrics: PerformanceMetrics
    cost_drag_bps: float       # average annualised drag from costs

    def summary(self) -> dict:
        m = self.metrics.to_dict()
        m["cost_drag_bps"] = self.cost_drag_bps
        return m


@dataclass
class BacktestEngine:
    """Vectorised backtester.

    The engine deliberately avoids event-loop style simulation: each pair's
    full path is computed in a few pandas ops, then aggregated.  This keeps
    runs fast enough that we can iterate parameters in the Notebooks.
    """

    cost_model: CostModel = field(default_factory=CostModel)
    signal_cfg: SignalConfig = field(default_factory=SignalConfig)
    risk_overlay: EventRiskOverlay | None = None
    initial_equity: float = 1.0
    pair_weight: str = "equal"  # only equal-weight is supported for now

    def run(
        self,
        prices: pd.DataFrame,
        pairs: Sequence[PairCandidate],
        events: pd.DataFrame | None = None,
    ) -> BacktestResult:
        if not pairs:
            log.warning("backtest called with zero pairs; returning empty result")
            empty = pd.Series(dtype=float)
            return BacktestResult(
                equity=empty,
                returns=empty,
                positions=pd.DataFrame(),
                pair_pnl=pd.DataFrame(),
                metrics=compute_metrics(empty),
                cost_drag_bps=0.0,
            )

        events = events if events is not None else pd.DataFrame()
        if not events.empty:
            events = events.copy()
            events["event_date"] = pd.to_datetime(events["event_date"])

        per_pair_pnl: dict[str, pd.Series] = {}
        per_pair_positions: list[pd.DataFrame] = []
        per_pair_turnover: list[pd.Series] = []
        per_pair_cost: list[pd.Series] = []

        # Each pair gets 1 / N of the initial equity as its notional bucket.
        notional = self.initial_equity / len(pairs)

        for pair in pairs:
            sig = generate_signals(prices, pair, cfg=self.signal_cfg)
            if sig.empty:
                continue
            pos = build_positions(sig, prices, pair, pair_notional=notional)
            if pos.empty:
                continue
            if self.risk_overlay is not None and not events.empty:
                pos = self.risk_overlay.apply(pos, events, (pair.code_a, pair.code_b))

            wide = prices.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
            pa = wide[pair.code_a].reindex(pos.index).ffill()
            pb = wide[pair.code_b].reindex(pos.index).ffill()

            # Daily simple returns of each leg.
            ret_a = pa.pct_change().fillna(0.0)
            ret_b = pb.pct_change().fillna(0.0)

            # PnL = signed notional held *previous* day * today's return.
            wa_lag = pos["w_a"].shift(1).fillna(0.0)
            wb_lag = pos["w_b"].shift(1).fillna(0.0)
            pnl = wa_lag * ret_a + wb_lag * ret_b

            # Cost: from change in notional (= turnover) per leg.
            dw_a = pos["w_a"].diff().fillna(pos["w_a"])
            dw_b = pos["w_b"].diff().fillna(pos["w_b"])
            cost_series = self.cost_model.cost_per_turnover(dw_a) + self.cost_model.cost_per_turnover(dw_b)
            pnl_net = pnl - cost_series

            per_pair_pnl[pair.pair_id] = pnl_net
            df_pos = pos.assign(pair_id=pair.pair_id).reset_index().rename(columns={"index": "trade_date"})
            per_pair_positions.append(df_pos)
            per_pair_turnover.append(dw_a.abs() + dw_b.abs())
            per_pair_cost.append(cost_series)

        if not per_pair_pnl:
            empty = pd.Series(dtype=float)
            return BacktestResult(
                equity=empty,
                returns=empty,
                positions=pd.DataFrame(),
                pair_pnl=pd.DataFrame(),
                metrics=compute_metrics(empty),
                cost_drag_bps=0.0,
            )

        pair_pnl = pd.concat(per_pair_pnl, axis=1).fillna(0.0)
        port_pnl = pair_pnl.sum(axis=1)
        port_ret = port_pnl / self.initial_equity
        equity = self.initial_equity + port_pnl.cumsum()

        positions_long = pd.concat(per_pair_positions, ignore_index=True)
        total_turnover = pd.concat(per_pair_turnover, axis=1).sum(axis=1) / self.initial_equity
        total_cost = pd.concat(per_pair_cost, axis=1).sum(axis=1)
        cost_drag_bps = float(total_cost.sum() / self.initial_equity * 1e4 / max(1, len(port_ret) / 244))

        metrics = compute_metrics(port_ret, turnover=total_turnover)
        log.info(
            "backtest done | pairs={} | sharpe={:.2f} | cagr={:.2%} | mdd={:.2%}",
            len(per_pair_pnl),
            metrics.sharpe,
            metrics.cagr,
            metrics.max_drawdown,
        )
        return BacktestResult(
            equity=equity,
            returns=port_ret,
            positions=positions_long,
            pair_pnl=pair_pnl,
            metrics=metrics,
            cost_drag_bps=cost_drag_bps,
        )
