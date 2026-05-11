"""Cointegration tests for pairs trading.

We implement two complementary tests:

- **Engle-Granger** (residual-based): OLS-regress :math:`p_b` on :math:`p_a`,
  then run an ADF test on the residuals.  Hedge ratio (beta) comes directly
  from the OLS slope.
- **Johansen** (system-based): vectorised on (price_a, price_b); used as a
  cross-check.  Optional - falls back to Engle-Granger only when statsmodels
  is missing this feature.

Mean-reversion half-life
------------------------
Estimated from an AR(1) on residual differences: ``Δu_t = θ * u_{t-1} + ε_t``
gives ``half_life = -ln(2) / θ`` when θ < 0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint

from core.logger import get_logger

log = get_logger(__name__)


@dataclass
class CointegrationResult:
    """Output of :func:`engle_granger`.

    Attributes
    ----------
    pvalue
        Engle-Granger p-value (lower = more cointegrated).
    hedge_ratio
        OLS slope (beta) such that ``b ~ alpha + beta * a + u``.
    intercept
        OLS intercept (alpha).
    residuals
        Residual series (mean-reverting spread).
    adf_stat
        ADF test statistic on residuals (more negative = more stationary).
    half_life
        Estimated half-life in trading days; ``np.nan`` when not mean-reverting.
    """

    pvalue: float
    hedge_ratio: float
    intercept: float
    residuals: pd.Series
    adf_stat: float
    half_life: float


def engle_granger(a: pd.Series, b: pd.Series) -> CointegrationResult:
    """Run an Engle-Granger cointegration test on two price series.

    Parameters
    ----------
    a, b
        Price series indexed by date (already aligned).  Length must match.

    Notes
    -----
    We use ``statsmodels.tsa.stattools.coint`` for the standard p-value, then
    re-run OLS to recover the hedge ratio (Engle-Granger conveniently uses the
    same regression internally but does not expose the coefficients).
    """
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    if len(a) < 60:
        # ADF is noisy on tiny samples; pairs trading literature usually wants
        # at least one trading quarter of history.
        log.debug("series too short for cointegration test: {} obs", len(a))

    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    # Drop NaNs jointly.
    mask = ~np.isnan(a_arr) & ~np.isnan(b_arr)
    a_arr, b_arr = a_arr[mask], b_arr[mask]

    # Engle-Granger p-value (statsmodels regresses ``y1`` on ``y2`` then ADFs the residual)
    _, pvalue, _ = coint(b_arr, a_arr)

    # Recover beta/alpha via OLS so we can also output the spread series.
    X = sm.add_constant(a_arr)
    ols = sm.OLS(b_arr, X).fit()
    intercept, beta = float(ols.params[0]), float(ols.params[1])
    resid = b_arr - (intercept + beta * a_arr)
    adf_stat, _, _, _, _, _ = adfuller(resid, autolag="AIC")
    hl = half_life(pd.Series(resid))

    return CointegrationResult(
        pvalue=float(pvalue),
        hedge_ratio=beta,
        intercept=intercept,
        residuals=pd.Series(resid, index=a.index[mask]),
        adf_stat=float(adf_stat),
        half_life=hl,
    )


def half_life(spread: pd.Series) -> float:
    """Estimate mean-reversion half-life via Δu ~ θ u_{t-1}.

    Returns ``np.nan`` when θ >= 0 (non-mean-reverting) or fit fails.
    """
    spread = spread.dropna()
    if len(spread) < 10:
        return float("nan")
    diff = spread.diff().dropna()
    lag = spread.shift(1).dropna()
    aligned = pd.concat([diff, lag], axis=1, join="inner")
    aligned.columns = ["dy", "y_lag"]
    if aligned.empty:
        return float("nan")
    try:
        X = sm.add_constant(aligned["y_lag"])
        theta = sm.OLS(aligned["dy"], X).fit().params["y_lag"]
        if theta >= 0:
            return float("nan")
        return float(-np.log(2) / theta)
    except Exception as e:
        log.debug("half_life fit failed: {}", e)
        return float("nan")


def johansen(a: pd.Series, b: pd.Series, lag: int = 1) -> dict:
    """Optional Johansen test (cross-check).  Returns ``{"trace": ..., "r": ...}``.

    Falls back to ``{"trace": nan, "r": 0}`` if the optional API is missing.
    """
    try:
        from statsmodels.tsa.vector_ar.vecm import coint_johansen

        df = pd.concat([a, b], axis=1).dropna()
        res = coint_johansen(df.values, det_order=0, k_ar_diff=lag)
        # Compare trace stat to 5% critical value for r=0.
        trace = float(res.lr1[0])
        crit5 = float(res.cvt[0, 1])  # column 1 is the 95% c.v.
        return {"trace": trace, "crit5": crit5, "r": int(trace > crit5)}
    except Exception as e:
        log.debug("Johansen unavailable: {}", e)
        return {"trace": float("nan"), "crit5": float("nan"), "r": 0}
