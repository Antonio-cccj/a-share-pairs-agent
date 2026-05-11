"""Rolling Z-score signal generator.

For each cointegrated pair the spread is::

    spread_t = p_b_t - (alpha + beta * p_a_t)

We normalise this by a rolling mean/std (default 60 days), then translate
threshold crossings into open/close trade flags:

- Long-spread (buy B, sell beta * A) when ``z < -open_z``.
- Short-spread (sell B, buy beta * A) when ``z > +open_z``.
- Flat when ``|z| < close_z`` after a position is on.

Stop-out happens at ``|z| > stop_z`` (default 3.5).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.logger import get_logger
from strategy.pair_selection import PairCandidate

log = get_logger(__name__)


@dataclass
class SignalConfig:
    """Tunable thresholds for the Z-score crossover strategy."""

    open_z: float = 2.0
    close_z: float = 0.5
    stop_z: float = 3.5
    rolling: int = 60          # window for mean/std
    min_history: int = 60      # bars needed before any trade


def generate_signals(
    prices: pd.DataFrame,
    pair: PairCandidate,
    cfg: SignalConfig | None = None,
) -> pd.DataFrame:
    """Generate a +1 / 0 / -1 position series for the supplied *pair*.

    Returns a DataFrame indexed by trade_date with columns::

        ['spread', 'z', 'pos', 'reason']

    where ``pos`` is ``+1`` for *long-spread* (B - beta*A), ``-1`` for
    *short-spread*, and ``0`` for flat.
    """
    cfg = cfg or SignalConfig()
    wide = prices.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
    if pair.code_a not in wide.columns or pair.code_b not in wide.columns:
        return pd.DataFrame()

    pa, pb = wide[pair.code_a], wide[pair.code_b]
    paired = pd.concat([pa, pb], axis=1, join="inner").dropna()
    paired.columns = ["pa", "pb"]
    if paired.empty:
        return pd.DataFrame()

    spread = paired["pb"] - (pair.intercept + pair.hedge_ratio * paired["pa"])
    rmean = spread.rolling(cfg.rolling, min_periods=cfg.min_history).mean()
    rstd = spread.rolling(cfg.rolling, min_periods=cfg.min_history).std()
    z = (spread - rmean) / rstd

    pos = pd.Series(0, index=z.index, dtype=int)
    reason = pd.Series("", index=z.index)
    current = 0
    for t in range(len(z)):
        zt = z.iloc[t]
        if np.isnan(zt):
            pos.iloc[t] = current
            continue
        # Stop-out overrides everything.
        if abs(zt) > cfg.stop_z and current != 0:
            current = 0
            reason.iloc[t] = "stopout"
        # Close if we're inside the close band.
        elif current != 0 and abs(zt) < cfg.close_z:
            current = 0
            reason.iloc[t] = "close"
        # Open from flat.
        elif current == 0 and zt > cfg.open_z:
            current = -1  # short the spread
            reason.iloc[t] = "open_short_spread"
        elif current == 0 and zt < -cfg.open_z:
            current = +1  # long the spread
            reason.iloc[t] = "open_long_spread"
        pos.iloc[t] = current

    out = pd.DataFrame(
        {
            "spread": spread,
            "z": z,
            "pos": pos,
            "reason": reason,
        }
    )
    log.debug(
        "signals for {}: trades={}",
        pair.pair_id,
        int((pos.diff().abs() > 0).sum()),
    )
    return out
