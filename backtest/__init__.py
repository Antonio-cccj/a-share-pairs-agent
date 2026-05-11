"""Backtest engine + performance metrics.

- :mod:`backtest.engine`       - vectorised daily pair-trade simulator.
- :mod:`backtest.costs`        - commission, stamp duty, slippage models.
- :mod:`backtest.metrics`      - Sharpe, Calmar, MDD, hit ratio, etc.
- :mod:`backtest.risk_overlay` - event-driven position throttler.
"""

from backtest.costs import CostModel  # noqa: F401
from backtest.engine import BacktestEngine, BacktestResult  # noqa: F401
from backtest.metrics import compute_metrics  # noqa: F401
from backtest.risk_overlay import EventRiskOverlay  # noqa: F401
