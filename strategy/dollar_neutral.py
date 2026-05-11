"""Beta-neutral, dollar-neutral position sizing.

Given a unit-notional budget ``N`` per pair and the hedge ratio ``beta``,
we size the legs so the resulting portfolio is **both**:

- *Dollar-neutral*: long notional == short notional, and
- *Beta-neutral*: the OLS hedge ratio is honoured.

Concretely, for a +1 long-spread signal (long B, short A) at prices :math:`p_a`,
:math:`p_b`::

    weight_b = +N / (1 + beta * p_a / p_b)
    weight_a = -beta * weight_b * (p_a / p_b)

so that ``weight_b * p_b`` (long leg value) equals ``-weight_a * p_a``
(short leg value), giving zero net exposure in CNY terms.
"""

from __future__ import annotations

import pandas as pd

from strategy.pair_selection import PairCandidate


def build_positions(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    pair: PairCandidate,
    pair_notional: float = 1.0,
) -> pd.DataFrame:
    """Map ``signals['pos']`` into per-leg position weights.

    Parameters
    ----------
    signals
        Output of :func:`strategy.zscore_signal.generate_signals`.
    prices
        Long-format OHLCV; we use ``close`` only.
    pair
        Cointegration result describing the hedge ratio.
    pair_notional
        Total *gross* notional (long + short value) per pair in arbitrary units.
        For backtest equity scaling, set this to ``equity / n_active_pairs``.

    Returns
    -------
    DataFrame indexed by trade_date with columns::

        ['w_a', 'w_b', 'pos']

    where ``w_a`` and ``w_b`` are *signed* notionals (negative = short).
    """
    if signals.empty:
        return pd.DataFrame(columns=["w_a", "w_b", "pos"])
    wide = prices.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
    if pair.code_a not in wide.columns or pair.code_b not in wide.columns:
        return pd.DataFrame(columns=["w_a", "w_b", "pos"])

    p = wide[[pair.code_a, pair.code_b]].dropna().reindex(signals.index).ffill()
    p.columns = ["pa", "pb"]
    sig = signals["pos"].astype(float)

    # Half of the gross notional on each leg.
    leg = pair_notional / 2.0
    # We invest `leg` CNY on each leg, in shares of the respective stock.
    units_b = sig * (leg / p["pb"])
    units_a = -sig * pair.hedge_ratio * (leg / p["pa"])

    # Convert to signed CNY weights (helpful for downstream PnL & cost accounting).
    w_a = units_a * p["pa"]
    w_b = units_b * p["pb"]

    return pd.DataFrame({"w_a": w_a, "w_b": w_b, "pos": sig.astype(int)})
