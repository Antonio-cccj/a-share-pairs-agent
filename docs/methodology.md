# Methodology

## 1. Cointegration

设两支股票 :math:`p_a, p_b`，先做 OLS：

```
p_b = α + β * p_a + u
```

Run an ADF stationarity test on residual :math:`u`. If stationarity holds, :math:`p_a, p_b` are cointegrated.

`hedge_ratio = β`，`half_life = -ln(2) / θ`（其中 :math:`Δu_t = θ u_{t-1} + ε`）。

Screening rules:

- p-value < 0.05 (CLI allows 0.10 for sample-data demonstrations)
- 2 ≤ half_life ≤ 90 trading days
- same-industry pairing prior

## 2. Z-score signal

```
spread_t = p_b - (α + β * p_a)
z_t      = (spread_t - rolling_mean) / rolling_std
```

Thresholds:

- open when `|z| > 2.0 sigma`
- close when `|z| < 0.5 sigma`
- stop-loss when `|z| > 3.5 sigma`

## 3. Position sizing

Beta-neutral and dollar-neutral sizing. See `strategy/dollar_neutral.py` for implementation details.

## 4. Cost model

- 3 bps commission (both sides)
- 10 bps stamp duty (sell side)
- 5 bps slippage (both sides)

## 5. Nine-event taxonomy

See `agents/event_taxonomy.yaml`.  
The LLM prompt enforces one-of-nine classification and returns:
- severity in [0, 1]
- confidence in [0, 1]
- concise rationale

Risk overlay policy:
- severity >= 0.7: force flatten
- 0.4 <= severity < 0.7: reduce exposure by 30%
- cooldown: 5 trading days
