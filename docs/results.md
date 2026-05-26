# Sample Run Results

> Metrics below are produced from synthetic sample data and default parameters.
> They demonstrate pipeline behavior only, not live-trading performance.

## 1. Run commands

```bash
python scripts/init_db.py --use-samples
python scripts/run_backtest.py --use-samples --max-pairs 10
```

## 2. Example metrics output

`reports/output/metrics.json` sample:

```json
{
  "cagr": 0.148,
  "annual_vol": 0.033,
  "sharpe": 4.26,
  "sortino": 6.08,
  "calmar": 13.81,
  "max_drawdown": -0.011,
  "win_rate": 0.61,
  "avg_win_loss": 1.80,
  "n_trades": 637,
  "turnover": 13.25,
  "cost_drag_bps": 172.2
}
```

Synthetic data contains intentionally structured relationships, so Sharpe can be inflated
relative to realistic market conditions.

## 3. With event overlay

```bash
python scripts/run_backtest.py --use-samples --with-risk-overlay --max-pairs 10
```

The event overlay can reduce or flatten positions, typically increasing turnover and costs,
while improving drawdown behavior in risk-heavy windows.
