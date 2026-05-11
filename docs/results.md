# 示例运行结果 / Sample run results

> 业绩为内置 *合成数据* + *默认参数* 下的运行结果，仅用于演示流水线，
> 不代表真实回测业绩，不构成投资建议。

## 一、运行命令

```bash
python scripts/init_db.py --use-samples
python scripts/run_backtest.py --use-samples --max-pairs 10
```

## 二、产出指标 (示例)

`reports/output/metrics.json` 示例（一次合成数据运行）：

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

**注意**：合成数据的协整关系是“刻意嵌入”的，因此 Sharpe 偏高；
真实 A 股数据上业绩会显著低于此值。

## 三、含事件叠加 / With event overlay

```bash
python scripts/run_backtest.py --use-samples --with-risk-overlay --max-pairs 10
```

事件叠加会触发减仓/平仓，因此换手与成本上升，Sharpe 通常下降但 MDD 改善。
