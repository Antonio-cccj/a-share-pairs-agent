# 方法论 / Methodology

## 一、协整检验 / Cointegration

设两支股票 :math:`p_a, p_b`，先做 OLS：

```
p_b = α + β * p_a + u
```

对残差 :math:`u` 做 ADF 单位根检验，若拒绝原假设则可认为 :math:`u` 平稳，
即 :math:`p_a, p_b` 协整。

`hedge_ratio = β`，`half_life = -ln(2) / θ`（其中 :math:`Δu_t = θ u_{t-1} + ε`）。

筛选规则：

- p-value < 0.05（CLI 默认放宽到 0.10 以便样本数据演示）
- 2 ≤ half_life ≤ 90 trading days
- 行业内成对（economic prior）

## 二、Z-Score 信号 / Z-Score signal

```
spread_t = p_b - (α + β * p_a)
z_t      = (spread_t - rolling_mean) / rolling_std
```

阈值：

- 开仓 `|z| > 2.0σ`（多/空 spread 方向相反）
- 平仓 `|z| < 0.5σ`
- 止损 `|z| > 3.5σ`

## 三、仓位 / Position sizing

Beta 中性 + Dollar-Neutral，详见 `strategy/dollar_neutral.py` docstring。
直观上：长 1 元 B 同时 short β·(p_a/p_b) 元 A。

## 四、成本模型 / Cost model

- 佣金 3 bp（双边）
- 印花税 10 bp（卖出方）
- 滑点 5 bp（双边）

往返综合约 26 bp，是 A 股相对真实的交易摩擦水平。

## 五、9 类事件分类 / 9-event taxonomy

参见 `agents/event_taxonomy.yaml`。LLM 的 system prompt 强制把公告
归入 9 类之一，并要求输出严重度 ∈ [0, 1]、置信度 ∈ [0, 1]、原因句。
当严重度 ≥ 0.7 时风险叠加层强制平仓；0.4 ≤ severity < 0.7 时按
30% 比例减仓；冷却 5 个交易日。
