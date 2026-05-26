"""CLI: end-to-end backtest with optional event-risk overlay.

Usage
-----
::

    python scripts/run_backtest.py --use-samples
    python scripts/run_backtest.py --use-samples --with-risk-overlay
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from backtest import BacktestEngine, CostModel, EventRiskOverlay  # noqa: E402
from core.config import settings  # noqa: E402
from core.data import IngestService  # noqa: E402
from core.logger import get_logger  # noqa: E402
from strategy import screen_pairs  # noqa: E402
from strategy.zscore_signal import SignalConfig  # noqa: E402

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-samples", action="store_true")
    parser.add_argument("--with-risk-overlay", action="store_true")
    parser.add_argument("--max-pairs", type=int, default=20)
    parser.add_argument("--out-dir", type=Path, default=Path("reports/output"))
    parser.add_argument("--no-plot", action="store_true", help="Skip writing PNG charts (CI).")
    args = parser.parse_args(argv)

    settings.ensure_dirs()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    svc = IngestService()
    prices = svc.load_ohlcv()
    if prices.empty:
        log.warning("OHLCV table empty - running scripts/init_db.py automatically")
        from scripts.init_db import main as init_main

        init_main(["--use-samples"] if args.use_samples else [])
        prices = svc.load_ohlcv()
    # Read stocks for industry grouping (samples loader writes it).
    from sqlalchemy import text

    with svc.engine.begin() as conn:
        stocks = pd.read_sql(text("SELECT * FROM stocks"), conn)

    log.info("loaded prices: rows={} stocks={}", len(prices), len(prices["ts_code"].unique()))
    pairs = screen_pairs(prices, stocks, pvalue_threshold=0.10, max_pairs=args.max_pairs)
    log.info("screened pairs={}", len(pairs))
    if not pairs:
        log.error("no cointegrated pairs found; aborting")
        return 1

    events = pd.DataFrame()
    if args.with_risk_overlay:
        # Run the event agent on the announcements table to populate events.
        from agents.event_rag_agent import EventRAGAgent

        agent = EventRAGAgent(ingest=svc)
        agent.run_batch()
        with svc.engine.begin() as conn:
            events = pd.read_sql(text("SELECT * FROM events"), conn)
        log.info("events available: {}", len(events))

    overlay = EventRiskOverlay() if args.with_risk_overlay else None
    engine = BacktestEngine(
        cost_model=CostModel(
            commission_bps=settings.backtest_commission_bps,
            stamp_duty_bps=settings.backtest_stamp_duty_bps,
            slippage_bps=settings.backtest_slippage_bps,
        ),
        signal_cfg=SignalConfig(),
        risk_overlay=overlay,
    )
    result = engine.run(prices, pairs, events=events if not events.empty else None)

    # Persist artefacts.
    summary = result.summary()
    log.info("metrics: {}", summary)
    (args.out_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    result.equity.to_csv(args.out_dir / "equity.csv", header=["equity"])
    result.returns.to_csv(args.out_dir / "returns.csv", header=["ret"])
    result.positions.to_csv(args.out_dir / "positions.csv", index=False)

    if not args.no_plot:
        try:
            fig, ax = plt.subplots(figsize=(10, 4))
            result.equity.plot(ax=ax, color="steelblue")
            ax.set_title("Equity curve - pairs strategy")
            ax.set_ylabel("NAV")
            fig.tight_layout()
            fig.savefig(args.out_dir / "equity.png", dpi=120)
            plt.close(fig)
            log.info("wrote {}", args.out_dir / "equity.png")
        except Exception as e:
            log.warning("plot skipped: {}", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
