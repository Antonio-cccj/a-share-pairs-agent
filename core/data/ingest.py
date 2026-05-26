"""Database ingest service.

Coordinates Tushare → akshare → samples fallback chain and persists the result
into SQLite/Postgres via SQLAlchemy.

Design choices
--------------
- One service object holds a single SQLAlchemy engine; transactions per
  ``with engine.begin()`` block (SQLAlchemy 2.x style).
- Schema lives in ``schema.sql`` and is executed on first call to
  :meth:`init_schema`.  We do NOT use ORM-level metadata generation: keeping
  the DDL in plain SQL makes it portable across SQLite/PG and easy to review.
- All public methods accept ``pd.DataFrame`` and use ``to_sql(..., method='multi')``
  for performance.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.config import settings
from core.data.akshare_client import AkshareClient
from core.data.sample_loader import SampleLoader
from core.data.tushare_client import TushareClient
from core.logger import get_logger

log = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# SQLite has a default 999-variable limit per statement.  We chunk inserts so
# each batch stays well under that ceiling regardless of column count.
_SQLITE_MAX_VARS = 900


def _safe_chunksize(n_cols: int) -> int:
    """Largest insert chunk that fits in SQLite's variable budget."""
    return max(1, _SQLITE_MAX_VARS // max(1, n_cols))


class IngestService:
    """High-level wrapper around the three data sources + the database."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.database_url
        # SQLite filename must exist before connect (engine wants the dir).
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", "", 1))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(self.database_url, future=True)
        self.tushare = TushareClient()
        self.akshare = AkshareClient()
        self.samples = SampleLoader()

    # ---------------------------------------------------------------- schema
    def init_schema(self) -> None:
        """Execute schema.sql.  Safe to call repeatedly (uses ``IF NOT EXISTS``)."""
        ddl = _SCHEMA_PATH.read_text(encoding="utf-8")
        log.info("initialising schema at {}", self.database_url)
        with self.engine.begin() as conn:
            # SQLite needs statement-by-statement execution; split on `;\n`.
            for stmt in [s.strip() for s in ddl.split(";\n") if s.strip()]:
                conn.execute(text(stmt))

    # -------------------------------------------------------------- ingest API
    def ingest_universe(self, use_samples: bool = False) -> int:
        """Populate the ``stocks`` table; returns the row count inserted."""
        df = self._fetch_universe(use_samples)
        if df is None or df.empty:
            log.warning("universe empty after fallback chain")
            return 0
        with self.engine.begin() as conn:
            # Idempotency: clear and reinsert.  For prod we'd use UPSERT but
            # sample/dev runs are simpler this way.
            conn.execute(text("DELETE FROM stocks"))
            df.to_sql("stocks", conn, if_exists="append", index=False)
        log.info("ingested universe rows={}", len(df))
        return len(df)

    def ingest_ohlcv(
        self,
        codes: Iterable[str],
        start: str | None = None,
        endd: str | None = None,
        use_samples: bool = False,
    ) -> int:
        """Insert daily OHLCV for *codes*.  Returns total rows inserted."""
        start = start or settings.backtest_start
        endd = endd or settings.backtest_end
        df = self._fetch_ohlcv(list(codes), start, endd, use_samples)
        if df.empty:
            return 0
        with self.engine.begin() as conn:
            # SQLite lacks ON CONFLICT for older versions; brute clear & insert.
            for code in df["ts_code"].unique():
                conn.execute(
                    text(
                        "DELETE FROM ohlcv_daily WHERE ts_code = :c AND trade_date BETWEEN :s AND :e"
                    ),
                    {"c": code, "s": start, "e": endd},
                )
            df.to_sql(
                "ohlcv_daily",
                conn,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=_safe_chunksize(len(df.columns)),
            )
        log.info("ingested ohlcv rows={} codes={}", len(df), len(df["ts_code"].unique()))
        return len(df)

    def ingest_announcements(
        self,
        codes: Iterable[str],
        start: str | None = None,
        endd: str | None = None,
        use_samples: bool = False,
    ) -> int:
        """Insert announcements for *codes*; uses samples when no source online."""
        start = start or settings.backtest_start
        endd = endd or settings.backtest_end
        codes = list(codes)

        if use_samples or not self.tushare.available:
            df = self.samples.announcements(codes, start, endd)
        else:
            frames = []
            for c in codes:
                d = self.tushare.anns(c, start, endd)
                if d is not None and not d.empty:
                    frames.append(d)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            if df.empty:
                log.warning("tushare anns_d returned empty; falling back to samples")
                df = self.samples.announcements(codes, start, endd)

        if df.empty:
            return 0
        with self.engine.begin() as conn:
            df.to_sql(
                "announcements",
                conn,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=_safe_chunksize(len(df.columns)),
            )
        log.info("ingested announcements rows={}", len(df))
        return len(df)

    # -------------------------------------------------------------- read API
    def load_ohlcv(
        self,
        codes: Iterable[str] | None = None,
        start: str | None = None,
        endd: str | None = None,
    ) -> pd.DataFrame:
        """Return tidy ``ts_code, trade_date, close`` (+OHLV) frame."""
        codes = list(codes) if codes else None
        q = "SELECT * FROM ohlcv_daily"
        clauses, params = [], {}
        if codes:
            placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
            clauses.append(f"ts_code IN ({placeholders})")
            params.update({f"c{i}": c for i, c in enumerate(codes)})
        if start:
            clauses.append("trade_date >= :s")
            params["s"] = start
        if endd:
            clauses.append("trade_date <= :e")
            params["e"] = endd
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY ts_code, trade_date"
        with self.engine.begin() as conn:
            df = pd.read_sql(text(q), conn, params=params)
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    def load_announcements(
        self, codes: Iterable[str] | None = None, start: str | None = None, endd: str | None = None
    ) -> pd.DataFrame:
        q, params = "SELECT * FROM announcements", {}
        clauses = []
        codes = list(codes) if codes else None
        if codes:
            placeholders = ", ".join(f":c{i}" for i in range(len(codes)))
            clauses.append(f"ts_code IN ({placeholders})")
            params.update({f"c{i}": c for i, c in enumerate(codes)})
        if start:
            clauses.append("ann_date >= :s")
            params["s"] = start
        if endd:
            clauses.append("ann_date <= :e")
            params["e"] = endd
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        with self.engine.begin() as conn:
            df = pd.read_sql(text(q), conn, params=params)
        return df

    # ------------------------------------------------------------ private
    def _fetch_universe(self, use_samples: bool) -> pd.DataFrame:
        if use_samples:
            return self.samples.stocks()
        if self.tushare.available:
            df = self.tushare.stock_basic()
            if df is not None and not df.empty:
                return df
            log.warning("tushare returned empty; trying akshare")
        if self.akshare.available:
            try:
                return self.akshare.stock_basic()
            except Exception as e:
                log.warning("akshare stock_basic failed: {}", e)
        log.warning("falling back to sample universe")
        return self.samples.stocks()

    def _fetch_ohlcv(
        self, codes: list[str], start: str, endd: str, use_samples: bool
    ) -> pd.DataFrame:
        if use_samples:
            return self.samples.ohlcv(codes, start, endd)
        if self.tushare.available:
            frames = []
            for c in codes:
                df = self.tushare.daily(c, start, endd)
                if df is not None and not df.empty:
                    frames.append(df)
            if frames:
                return pd.concat(frames, ignore_index=True)
            log.warning("tushare yielded no OHLCV; trying akshare")
        if self.akshare.available:
            frames = []
            for c in codes:
                try:
                    df = self.akshare.daily(c, start, endd)
                    if not df.empty:
                        frames.append(df)
                except Exception as e:
                    log.warning("akshare daily failed for {}: {}", c, e)
            if frames:
                return pd.concat(frames, ignore_index=True)
        log.warning("falling back to synthetic samples for OHLCV")
        return self.samples.ohlcv(codes, start, endd)
