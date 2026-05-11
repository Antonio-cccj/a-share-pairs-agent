"""Performance metrics for the pairs strategy.

All metrics operate on a *daily* return / equity series.  Annualisation
assumes 244 Chinese trading days per year.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 244


@dataclass
class PerformanceMetrics:
    cagr: float           # compound annual growth rate
    annual_vol: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    win_rate: float
    avg_win_loss: float
    n_trades: int
    turnover: float       # average annualised turnover (sum(|d|) / equity)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(
    returns: pd.Series,
    trades: Iterable[int] | None = None,
    turnover: pd.Series | None = None,
) -> PerformanceMetrics:
    """Compute the standard metrics block for a strategy.

    Parameters
    ----------
    returns
        Daily *fractional* returns (e.g. 0.01 = +1%).  NaNs are dropped.
    trades
        Optional iterable of round-trip PnL values to derive win-rate /
        avg-win-loss.  If ``None`` we approximate from sign of daily returns.
    turnover
        Optional daily fractional turnover series (``|d_w| / equity``).
    """
    r = pd.Series(returns).dropna().astype(float)
    if r.empty:
        return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    equity = (1.0 + r).cumprod()
    years = len(r) / TRADING_DAYS
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1) if years > 0 else 0.0
    vol = float(r.std() * np.sqrt(TRADING_DAYS))
    sharpe = float(r.mean() / r.std() * np.sqrt(TRADING_DAYS)) if r.std() > 0 else 0.0
    downside = r[r < 0]
    sortino = (
        float(r.mean() / downside.std() * np.sqrt(TRADING_DAYS))
        if not downside.empty and downside.std() > 0
        else 0.0
    )
    dd = _max_drawdown(equity)
    calmar = float(cagr / abs(dd)) if dd < 0 else 0.0

    if trades is None:
        wins = (r > 0).sum()
        losses = (r < 0).sum()
        win_rate = float(wins / max(1, wins + losses))
        avg_w = float(r[r > 0].mean()) if (r > 0).any() else 0.0
        avg_l = float(-r[r < 0].mean()) if (r < 0).any() else 0.0
        avg_wl = float(avg_w / avg_l) if avg_l > 0 else 0.0
        n_trades = int((r != 0).sum())
    else:
        trades_arr = np.asarray(list(trades), dtype=float)
        wins = (trades_arr > 0).sum()
        losses = (trades_arr < 0).sum()
        win_rate = float(wins / max(1, wins + losses))
        avg_w = float(trades_arr[trades_arr > 0].mean()) if (trades_arr > 0).any() else 0.0
        avg_l = float(-trades_arr[trades_arr < 0].mean()) if (trades_arr < 0).any() else 0.0
        avg_wl = float(avg_w / avg_l) if avg_l > 0 else 0.0
        n_trades = int(len(trades_arr))

    annualised_turnover = (
        float(turnover.mean() * TRADING_DAYS) if turnover is not None and not turnover.empty else 0.0
    )

    return PerformanceMetrics(
        cagr=cagr,
        annual_vol=vol,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=float(dd),
        win_rate=win_rate,
        avg_win_loss=avg_wl,
        n_trades=n_trades,
        turnover=annualised_turnover,
    )


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity / peak - 1.0).min()
    return float(dd)
