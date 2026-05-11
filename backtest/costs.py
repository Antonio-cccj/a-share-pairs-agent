"""Transaction-cost model.

A-share specifics
-----------------
- **Commission**: typically 3 bps (万分之三), symmetric.
- **Stamp duty**: 10 bps (千分之一), seller-side only.
- **Slippage**: a few bps depending on liquidity; we use a flat 5 bps as a
  conservative default.

All inputs are expressed in basis points (1 bp = 0.0001).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CostModel:
    """Vectorised cost calculator.

    Attributes
    ----------
    commission_bps : float
        Symmetric commission in bps (default 3).
    stamp_duty_bps : float
        Seller-side stamp duty in bps (default 10).
    slippage_bps : float
        One-way slippage in bps applied to every notional change (default 5).
    """

    commission_bps: float = 3.0
    stamp_duty_bps: float = 10.0
    slippage_bps: float = 5.0

    def cost_per_turnover(self, notional_delta: pd.Series) -> pd.Series:
        """Compute the CNY cost of *notional_delta* (signed change in CNY weight).

        Parameters
        ----------
        notional_delta
            Signed change in CNY notional per period (post-rebalance minus
            pre-rebalance).  Positive = bought, negative = sold.
        """
        # Convert basis points to fractions once.
        bps_to_frac = lambda bps: float(bps) / 1e4

        gross_turnover = notional_delta.abs()

        commission = gross_turnover * bps_to_frac(self.commission_bps)
        # Stamp duty applies only to the sell leg of the turnover.
        sell_turnover = np.where(notional_delta < 0, gross_turnover, 0.0)
        stamp = pd.Series(sell_turnover, index=notional_delta.index) * bps_to_frac(
            self.stamp_duty_bps
        )
        slippage = gross_turnover * bps_to_frac(self.slippage_bps)

        return commission + stamp + slippage

    def total_cost_bps(self, side: str = "round_trip") -> float:
        """Return effective bps drag.

        Useful for back-of-envelope sanity checks.
        """
        if side == "buy":
            return self.commission_bps + self.slippage_bps
        if side == "sell":
            return self.commission_bps + self.slippage_bps + self.stamp_duty_bps
        # Round trip.
        return 2 * self.commission_bps + 2 * self.slippage_bps + self.stamp_duty_bps
