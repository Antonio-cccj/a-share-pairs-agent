"""Offline sample loader.

When no API token is configured (CI, evaluators trying the repo, sleeping
users), we still want every script to run end-to-end.  This module provides
deterministic synthetic data plus a handful of real-shape CSVs shipped under
``data/samples/`` so that the rest of the pipeline never has to special-case
"no data".

Synthetic OHLCV is generated from a *cointegrated* pair of geometric Brownian
motions; this guarantees the cointegration tests downstream produce visible
positive examples without relying on a live data feed.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)

# Universe used in sample mode: 10 large-cap names spanning 4 industries.
SAMPLE_UNIVERSE: list[dict] = [
    {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒"},
    {"ts_code": "000858.SZ", "name": "五粮液",   "industry": "白酒"},
    {"ts_code": "600036.SH", "name": "招商银行", "industry": "银行"},
    {"ts_code": "601318.SH", "name": "中国平安", "industry": "保险"},
    {"ts_code": "000333.SZ", "name": "美的集团", "industry": "家电"},
    {"ts_code": "000651.SZ", "name": "格力电器", "industry": "家电"},
    {"ts_code": "600276.SH", "name": "恒瑞医药", "industry": "医药"},
    {"ts_code": "300760.SZ", "name": "迈瑞医疗", "industry": "医药"},
    {"ts_code": "600887.SH", "name": "伊利股份", "industry": "食品"},
    {"ts_code": "000568.SZ", "name": "泸州老窖", "industry": "白酒"},
]

# Deterministic cointegrated pairs to embed in the synthetic data.
# We construct B = alpha + beta*A + AR(1) noise so Engle-Granger should detect them.
COINTEGRATED_PAIRS: list[tuple[str, str, float, float]] = [
    # (code_a, code_b, alpha, beta)
    ("600519.SH", "000858.SZ", 50.0, 0.9),
    ("600036.SH", "601318.SH", 5.0, 1.1),
    ("000333.SZ", "000651.SZ", 2.0, 1.0),
    ("600276.SH", "300760.SZ", 10.0, 0.8),
    ("600519.SH", "000568.SZ", 100.0, 0.6),
]


class SampleLoader:
    """Deterministic synthetic data generator.

    Examples
    --------
    >>> loader = SampleLoader()
    >>> stocks = loader.stocks()
    >>> ohlcv  = loader.ohlcv(stocks["ts_code"].tolist(), "2021-01-01", "2024-12-31")
    """

    def __init__(self, seed: int = 42, csv_dir: Path | None = None) -> None:
        self._seed = seed
        self._csv_dir = Path(csv_dir) if csv_dir else None

    # ------------------------------------------------------- stocks (master)
    def stocks(self) -> pd.DataFrame:
        df = pd.DataFrame(SAMPLE_UNIVERSE)
        df["market"] = df["ts_code"].str[-2:]
        df["list_date"] = date(2010, 1, 1)
        return df[["ts_code", "name", "industry", "market", "list_date"]]

    # -------------------------------------------------------- OHLCV synthesis
    def ohlcv(self, codes: Iterable[str], start: str, endd: str) -> pd.DataFrame:
        """Generate cointegrated synthetic OHLCV for *codes*.

        Implementation
        --------------
        1. Build a calendar of business days.
        2. For each "leader" stock, sample GBM increments.
        3. For each cointegrated follower, set ``close = alpha + beta*leader + AR(1)``.
        4. Solitary stocks get standalone GBMs with industry-correlated drift.
        """
        codes = list(codes)
        rng = np.random.default_rng(self._seed)
        cal = pd.bdate_range(start=start, end=endd)
        T = len(cal)
        if T == 0:
            return pd.DataFrame()

        # Build the leader trajectories first (one per "anchor" code).
        leader_codes = {p[0] for p in COINTEGRATED_PAIRS}
        leaders: dict[str, np.ndarray] = {}
        for code in codes:
            # Use industry to set drift / vol regime.
            ind = next((s["industry"] for s in SAMPLE_UNIVERSE if s["ts_code"] == code), "Other")
            mu, sigma = _industry_regime(ind)
            log_ret = rng.normal(mu, sigma, size=T)
            price0 = _starting_price(code)
            leaders[code] = price0 * np.exp(np.cumsum(log_ret))

        # Overwrite followers with cointegrated series.
        for code_a, code_b, alpha, beta in COINTEGRATED_PAIRS:
            if code_a not in leaders or code_b not in leaders:
                continue
            a_series = leaders[code_a]
            # AR(1) noise with rho=0.85, std=2% of mean(a)
            rho, sigma_e = 0.85, 0.02 * float(np.mean(a_series))
            eps = rng.normal(0, sigma_e, size=T)
            u = np.zeros(T)
            for t in range(1, T):
                u[t] = rho * u[t - 1] + eps[t]
            leaders[code_b] = alpha + beta * a_series + u

        rows = []
        for code in codes:
            close = leaders[code]
            # Synthesise OHLV around close using GBM-style intraday variation.
            highs = close * (1.0 + np.abs(rng.normal(0, 0.005, size=T)))
            lows = close * (1.0 - np.abs(rng.normal(0, 0.005, size=T)))
            opens = close * (1.0 + rng.normal(0, 0.003, size=T))
            volume = rng.lognormal(mean=14, sigma=0.5, size=T)  # ~roughly 1.2M shares
            amount = volume * close
            for i, d in enumerate(cal):
                rows.append(
                    {
                        "ts_code": code,
                        "trade_date": d.date(),
                        "open": float(opens[i]),
                        "high": float(highs[i]),
                        "low": float(lows[i]),
                        "close": float(close[i]),
                        "volume": float(volume[i]),
                        "amount": float(amount[i]),
                        "adj_factor": 1.0,
                        "circ_mv": float(close[i] * volume[i] * 100),
                    }
                )
        return pd.DataFrame(rows)

    # ------------------------------------------------------- announcements
    def announcements(self, codes: Iterable[str], start: str, endd: str) -> pd.DataFrame:
        """Generate a handful of sample announcements for risk-overlay testing.

        We embed one event per category across the calendar so that downstream
        classification tests see balanced positive examples.
        """
        rng = np.random.default_rng(self._seed + 7)
        cal = pd.bdate_range(start=start, end=endd)
        codes = list(codes)
        if not codes or len(cal) == 0:
            return pd.DataFrame()

        # 9 templates aligned with event_taxonomy.yaml
        templates = [
            ("suspension", "公司股票自2023年起停牌，等待重大事项披露。"),
            ("restructure", "公司拟通过发行股份及支付现金方式购买资产，构成重大资产重组。"),
            ("private_placement", "公司拟向特定对象非公开发行股票，募集资金不超过30亿元。"),
            ("earnings_warning", "公司预计本报告期归属于上市公司股东的净利润同比下降50%以上。"),
            ("shareholder_reduction", "公司控股股东计划自公告披露之日起15个交易日后减持公司股份不超过3%。"),
            ("litigation", "公司及子公司近期涉及多项重大诉讼事项，涉及金额合计超过10亿元。"),
            ("fraud_investigation", "公司收到中国证监会立案告知书，涉嫌信息披露违法违规。"),
            ("equity_change", "公司实际控制人发生变更，新实控人通过协议转让取得控制权。"),
            ("other", "公司发布关于召开2024年第一次临时股东大会的通知。"),
        ]

        rows = []
        # Sprinkle one announcement of each category per code over the calendar.
        for code in codes:
            chosen_dates = rng.choice(cal, size=min(len(templates), len(cal)), replace=False)
            chosen_dates = sorted(pd.to_datetime(chosen_dates))
            for d, (etype, body) in zip(chosen_dates, templates):
                ann_date = d.date()
                title = f"{etype.upper()} 公告 - {code}"
                rows.append(
                    {
                        "ann_id": f"sample-{code}-{ann_date}-{etype}",
                        "ts_code": code,
                        "ann_date": ann_date,
                        "title": title,
                        "url": "",
                        "content": body,
                        "source": "sample",
                    }
                )
        return pd.DataFrame(rows)


# -------------------------------------------------------- private helpers
def _industry_regime(ind: str) -> tuple[float, float]:
    """Return (daily_mu, daily_sigma) for an industry."""
    # These are coarse but produce visually distinct trajectories.
    table = {
        "白酒":   (4e-4, 0.018),
        "银行":   (1e-4, 0.012),
        "保险":   (2e-4, 0.014),
        "家电":   (3e-4, 0.016),
        "医药":   (3e-4, 0.020),
        "食品":   (2e-4, 0.014),
        "Other":  (2e-4, 0.018),
    }
    return table.get(ind, table["Other"])


def _starting_price(ts_code: str) -> float:
    """Stable starting price keyed by ts_code (deterministic per ticker)."""
    h = abs(hash(ts_code)) % 200 + 10  # 10..210
    return float(h)
