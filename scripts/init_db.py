"""CLI: create schema + populate sample data.

Usage
-----
::

    python scripts/init_db.py --use-samples
    python scripts/init_db.py                 # uses Tushare/akshare if env is set
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/init_db.py` invocation from a fresh checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.data import IngestService  # noqa: E402
from core.logger import get_logger  # noqa: E402

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialise database & populate data")
    parser.add_argument(
        "--use-samples", action="store_true", help="Use synthetic samples (no API needed)."
    )
    parser.add_argument("--start", default=settings.backtest_start)
    parser.add_argument("--end", default=settings.backtest_end)
    args = parser.parse_args(argv)

    settings.ensure_dirs()

    svc = IngestService()
    svc.init_schema()
    n_stocks = svc.ingest_universe(use_samples=args.use_samples)
    if n_stocks == 0:
        log.error("universe empty - aborting")
        return 1
    # Pull the freshly inserted codes back to drive OHLCV / announcement ingest.
    stocks = svc.load_ohlcv()  # may be empty on first run
    codes = list(stocks["ts_code"].unique()) if not stocks.empty else None
    if codes is None:
        # Read directly from the stocks table.
        from sqlalchemy import text

        with svc.engine.begin() as conn:
            codes = [r[0] for r in conn.execute(text("SELECT ts_code FROM stocks")).fetchall()]

    svc.ingest_ohlcv(codes, start=args.start, endd=args.end, use_samples=args.use_samples)
    svc.ingest_announcements(codes, start=args.start, endd=args.end, use_samples=args.use_samples)
    log.info("init_db done | stocks={} | range=[{} .. {}]", n_stocks, args.start, args.end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
