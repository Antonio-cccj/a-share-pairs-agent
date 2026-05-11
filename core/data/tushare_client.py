"""Tushare Pro thin wrapper with retries, rate-limiting and graceful fallback.

Why a wrapper?
--------------
The raw ``tushare`` SDK throws bare exceptions, has no built-in rate-limit,
and silently rate-limits free-tier users.  This wrapper:

- Retries with exponential back-off on transient errors.
- Throttles to ``RATE_LIMIT_PER_MIN`` (default 480, well under the 500/min
  hard cap for paid tiers, conservative for free tiers).
- Returns ``None`` when ``TUSHARE_TOKEN`` is missing so that callers can fall
  back to akshare / sample data.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Any

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


RATE_LIMIT_PER_MIN = 480  # conservative limit
_WINDOW = 60.0


class TushareClient:
    """Lazy-initialised Tushare Pro wrapper.

    The Pro API object is created on first access so that simply importing the
    module does not crash when ``tushare`` is not installed (it is an optional
    dep for Python 3.13 users where the package wheel may lag).
    """

    def __init__(self, token: str | None = None) -> None:
        # Resolve token at construction (allow per-instance override for tests).
        self._token = token if token is not None else settings.tushare_token
        self._pro: Any = None
        self._call_times: deque[float] = deque()

    # ------------------------------------------------------------ availability
    @property
    def available(self) -> bool:
        """Whether the client is usable (token + import both work)."""
        if not self._token:
            return False
        try:
            import tushare  # noqa: F401 - import test
            return True
        except Exception:
            return False

    def _ensure_pro(self) -> Any:
        if self._pro is None:
            import tushare as ts  # local import; optional dep
            ts.set_token(self._token)
            self._pro = ts.pro_api()
            log.info("tushare pro client initialised")
        return self._pro

    # ---------------------------------------------------------------- throttle
    def _throttle(self) -> None:
        now = time.monotonic()
        # Drop timestamps older than 60s.
        while self._call_times and now - self._call_times[0] > _WINDOW:
            self._call_times.popleft()
        if len(self._call_times) >= RATE_LIMIT_PER_MIN:
            sleep = _WINDOW - (now - self._call_times[0])
            if sleep > 0:
                log.debug("tushare throttle sleep {:.2f}s", sleep)
                time.sleep(sleep)
        self._call_times.append(time.monotonic())

    # -------------------------------------------------------------- public API
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def stock_basic(self) -> pd.DataFrame | None:
        """Return the full A-share stock listing (~5,300 rows).

        Returns ``None`` when the client is not available.
        """
        if not self.available:
            log.warning("tushare unavailable; stock_basic returning None")
            return None
        self._throttle()
        pro = self._ensure_pro()
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,industry,market,list_date",
        )
        log.info("tushare.stock_basic -> {} rows", len(df))
        return df

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def daily(self, ts_code: str, start: str, endd: str) -> pd.DataFrame | None:
        """Adjusted daily OHLCV for one ticker.

        Note we request ``adj_factor`` separately because Tushare's ``pro_bar``
        sometimes returns adjusted prices inconsistently; we prefer raw + factor.
        """
        if not self.available:
            return None
        self._throttle()
        pro = self._ensure_pro()
        df = pro.daily(ts_code=ts_code, start_date=start.replace("-", ""), end_date=endd.replace("-", ""))
        if df is None or df.empty:
            return df
        # Adjust factor (may be slow for full-history queries; cache upstream).
        self._throttle()
        adj = pro.adj_factor(ts_code=ts_code, start_date=start.replace("-", ""), end_date=endd.replace("-", ""))
        if adj is not None and not adj.empty:
            df = df.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
        else:
            df["adj_factor"] = 1.0
        # Normalise the date column to ISO format for SQLite compatibility.
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df.sort_values("trade_date", inplace=True)
        return df

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def anns(self, ts_code: str, start: str, endd: str) -> pd.DataFrame | None:
        """Announcement headlines (``anns_d`` endpoint)."""
        if not self.available:
            return None
        self._throttle()
        pro = self._ensure_pro()
        try:
            df = pro.anns_d(
                ts_code=ts_code,
                start_date=start.replace("-", ""),
                end_date=endd.replace("-", ""),
            )
        except Exception as e:  # endpoint may not be available on free tier
            log.warning("tushare anns_d failed for {}: {}", ts_code, e)
            return None
        return df


def now_iso() -> str:
    """Helper used by ingest scripts when stamping rows."""
    return datetime.utcnow().isoformat()
