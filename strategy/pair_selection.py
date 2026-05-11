"""Cross-section pair screening.

Algorithm
---------
1. Group stocks by industry (so legs are economically related).
2. For every intra-industry combination, run :func:`engle_granger`.
3. Keep pairs with:
   - p-value < ``pvalue_threshold`` (default 0.05)
   - 5d <= half-life <= 60d (mean-reverts within a usable horizon)
4. Sort by p-value ascending; cap at ``max_pairs``.

The screen runs on a *formation window* (e.g. the first 252 days of data);
the trading window uses the resulting hedge ratios out-of-sample.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

import pandas as pd

from core.logger import get_logger
from strategy.cointegration import CointegrationResult, engle_granger

log = get_logger(__name__)


@dataclass
class PairCandidate:
    code_a: str
    code_b: str
    industry: str
    pvalue: float
    hedge_ratio: float
    intercept: float
    half_life: float
    adf_stat: float

    @property
    def pair_id(self) -> str:
        return f"{self.code_a}--{self.code_b}"


def screen_pairs(
    prices: pd.DataFrame,
    stocks: pd.DataFrame,
    *,
    pvalue_threshold: float = 0.05,
    half_life_range: tuple[float, float] = (2.0, 90.0),
    max_pairs: int = 50,
    same_industry_only: bool = True,
) -> list[PairCandidate]:
    """Select cointegrated pairs.

    Parameters
    ----------
    prices
        Long-format DataFrame with columns ``ts_code, trade_date, close``.
    stocks
        Master frame with ``ts_code, industry`` (used to group when
        ``same_industry_only=True``).
    """
    if prices.empty:
        return []
    wide = (
        prices.pivot(index="trade_date", columns="ts_code", values="close")
        .sort_index()
        .ffill()
        .dropna(axis=1, thresh=int(len(prices["trade_date"].unique()) * 0.9))
    )
    if wide.empty:
        log.warning("price pivot is empty after filtering")
        return []

    industry_map = stocks.set_index("ts_code")["industry"].to_dict() if "industry" in stocks.columns else {}
    if same_industry_only:
        groups: dict[str, list[str]] = {}
        for code in wide.columns:
            ind = industry_map.get(code, "Other")
            groups.setdefault(ind, []).append(code)
    else:
        groups = {"ALL": list(wide.columns)}

    candidates: list[PairCandidate] = []
    for ind, codes in groups.items():
        if len(codes) < 2:
            continue
        for a, b in combinations(sorted(codes), 2):
            series_a = wide[a].dropna()
            series_b = wide[b].dropna()
            joined = pd.concat([series_a, series_b], axis=1, join="inner")
            joined.columns = [a, b]
            if len(joined) < 60:
                continue
            try:
                res: CointegrationResult = engle_granger(joined[a], joined[b])
            except Exception as e:
                log.debug("EG failed for {} vs {}: {}", a, b, e)
                continue
            if res.pvalue > pvalue_threshold:
                continue
            if not (half_life_range[0] <= res.half_life <= half_life_range[1]):
                continue
            candidates.append(
                PairCandidate(
                    code_a=a,
                    code_b=b,
                    industry=ind,
                    pvalue=res.pvalue,
                    hedge_ratio=res.hedge_ratio,
                    intercept=res.intercept,
                    half_life=res.half_life,
                    adf_stat=res.adf_stat,
                )
            )

    candidates.sort(key=lambda c: c.pvalue)
    log.info("screened {} cointegrated pairs (threshold p<{})", len(candidates), pvalue_threshold)
    return candidates[:max_pairs]


def to_dataframe(pairs: Iterable[PairCandidate]) -> pd.DataFrame:
    """Convert candidate list to a tidy DataFrame for persistence."""
    return pd.DataFrame(
        [
            {
                "pair_id": p.pair_id,
                "code_a": p.code_a,
                "code_b": p.code_b,
                "industry": p.industry,
                "pvalue": p.pvalue,
                "hedge_ratio": p.hedge_ratio,
                "half_life": p.half_life,
            }
            for p in pairs
        ]
    )
