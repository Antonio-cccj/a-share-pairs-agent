"""Tests for strategy.cointegration."""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.cointegration import engle_granger, half_life


def test_engle_granger_detects_synthetic_cointegration():
    """A perfectly cointegrated pair should produce p < 0.05."""
    rng = np.random.default_rng(0)
    n = 500
    a_levels = 100 + np.cumsum(rng.normal(0, 1, n))
    # b = 5 + 1.2 * a + AR(1) noise
    noise = np.zeros(n)
    for t in range(1, n):
        noise[t] = 0.8 * noise[t - 1] + rng.normal(0, 1)
    b_levels = 5 + 1.2 * a_levels + noise

    a = pd.Series(a_levels, index=pd.date_range("2020-01-01", periods=n, freq="B"))
    b = pd.Series(b_levels, index=a.index)
    res = engle_granger(a, b)

    assert res.pvalue < 0.05, f"expected p<0.05, got {res.pvalue}"
    # Beta should be near 1.2.
    assert abs(res.hedge_ratio - 1.2) < 0.15, f"beta={res.hedge_ratio}"
    # Half life finite and positive.
    assert res.half_life > 0


def test_half_life_returns_long_or_nan_for_random_walk():
    """Random walks shouldn't produce a *short* half-life (only fast mean reversion).

    Theoretical: for a true RW the AR(1) coefficient is 0, giving infinite
    half-life; in finite samples it can be a large positive number or even
    a small negative theta from sampling noise.  We accept anything outside
    the "looks mean-reverting" range (< 60 days).
    """
    rng = np.random.default_rng(1)
    rw = pd.Series(np.cumsum(rng.normal(0, 1, 500)))
    hl = half_life(rw)
    assert np.isnan(hl) or hl > 60, f"half_life={hl}"
