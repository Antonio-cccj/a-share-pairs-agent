"""Akshare client - free fallback when Tushare Pro token is absent.

Akshare scrapes public APIs (Sina, Eastmoney, etc.) and therefore has a lower
quality bar than Tushare Pro (no consistent rate-limit, occasional schema
drift), but it requires no token and covers most A-share needs.

Only a subset of methods is exposed - just enough to keep the rest of the
pipeline working when Tushare is unavailable.
"""

from __future__ import annotations

import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)


class AkshareClient:
    """Lazy-loaded akshare wrapper (akshare import is heavy)."""

    def __init__(self) -> None:
        self._ak = None

    @property
    def available(self) -> bool:
        try:
            import akshare  # noqa: F401
            return True
        except Exception:
            return False

    def _ak_mod(self):
        if self._ak is None:
            import akshare as ak

            self._ak = ak
            log.info("akshare imported")
        return self._ak

    # ---------------------------------------------------------- public API
    def stock_basic(self) -> pd.DataFrame:
        """Return a DataFrame compatible with the Tushare ``stock_basic`` shape.

        Columns: ``ts_code, name, industry, market, list_date``.
        """
        ak = self._ak_mod()
        # akshare provides A-share spot data; we pick a stable endpoint.
        df = ak.stock_info_a_code_name()
        # Convert "000001" -> "000001.SZ" / "600000.SH" by exchange rule.
        df["ts_code"] = df["code"].apply(_infer_ts_code)
        df["industry"] = "Unknown"
        df["market"] = df["ts_code"].str[-2:]
        df["list_date"] = None
        df.rename(columns={"name": "name"}, inplace=True)
        return df[["ts_code", "name", "industry", "market", "list_date"]]

    def daily(self, ts_code: str, start: str, endd: str) -> pd.DataFrame:
        """Daily OHLCV via Eastmoney through akshare."""
        ak = self._ak_mod()
        symbol = ts_code.split(".")[0]
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start.replace("-", ""),
            end_date=endd.replace("-", ""),
            adjust="qfq",  # forward-adjusted; we treat adj_factor as 1.0
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(
            columns={
                "日期": "trade_date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        df["ts_code"] = ts_code
        df["adj_factor"] = 1.0
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df[["ts_code", "trade_date", "open", "high", "low", "close", "volume", "amount", "adj_factor"]]


def _infer_ts_code(code: str) -> str:
    """Infer Tushare-style ts_code from a 6-digit Chinese ticker."""
    code = str(code).zfill(6)
    if code.startswith(("60", "68", "9")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "20")):
        return f"{code}.SZ"
    return f"{code}.BJ"
