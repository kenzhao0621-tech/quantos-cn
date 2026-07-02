# BACKTEST_AUDIT — 回测审计

> 结论先行：存在两套回测。`model_validation_service` 的滚动验证是**真实且较完整**的（成本/滑点/涨停/RankIC/DSR/PBO/Purged K-Fold）；`gateway/backtest/screener_backtest.py` 的组合回测**收益计算真实但 benchmark 是伪造的**；事件回测收益硬编码。验证窗口受限于仅 6.5 个月历史。

## 1. 组合回测 `run_screener_portfolio_backtest`（PATCH/REWRITE 局部）

`gateway/backtest/screener_backtest.py`，经 `POST /api/v1/research/backtest` 暴露：

| 特性 | 状态 | 证据 |
|---|---|---|
| 数据 | ✅ DuckDB daily_bars 真实 | — |
| 信号 | ✅ 按历史 as_of_date 逐日跑 `ScreenerService.screen()` | L54–60 |
| 持有期 | T+1（信号日收盘 → 次日收盘） | L66–82 |
| 交易成本 | ✅ cost_bps=8 默认 | L19, L81 |
| 滑点 | ✅ slippage_bps=12 默认 | L20, L81 |
| 涨停不可买 | ⚠️ 仅"次日开盘跳空 ≥9.7% 跳过"，近似 | L77–79 |
| 跌停不可卖 / 停牌 | ❌ 未建模 | — |
| T+1 卖出限制 | ❌ 逐日换仓假设，未模拟持仓锁定 | — |
| Sharpe/回撤 | ✅ 从真实逐日净收益计算 | L97–106 |
| **benchmark** | ❌ **伪造**：`hs300_proxy = total_ret*0.6`、`equal_weight = *0.5`、`buy_hold = *0.4` | **L135–138** |
| PBO | ❌ 变体为同序列反转/子采样，非独立策略 | L133 |

**Phase 4 处置**：benchmark 用 `index_bars` 沪深300（000300.SH）真实区间收益；PBO 用参数网格真实变体；补跌停/停牌/持仓锁定。

## 2. 事件回测 `run_event_backtest`（REWRITE 或删除）

`gateway/backtest/event_engine.py`：PIT 完整性检查真实（L48–56），但收益 `rets = [0.01] * len(fills)` 硬编码（L87）。当前仅在客户端自带 bars/signals 时触发。**Phase 4 重写或移除。**

## 3. 滚动验证 `model_validation_service`（KEEP — 最接近目标形态）

`quant/application/model_validation_service.py`：

- 成本+滑点（可配置）、涨停禁买、跌停风险标记
- 行业中性 top-N 选择
- RankIC、DSR（deflated Sharpe）、PBO、Purged K-Fold、walk-forward
- 落盘 `artifacts/model_validation.json`，`POST /api/v1/models/validate` 触发

**缺口**：不自动跑（NOT_RUN 常态）；未与 benchmark 真实对比；窗口受 6.5 个月历史限制。

## 4. T+1 证明 `prove_next_day`（KEEP）

`screener_service.py` L887–973：真实的次日样本外验证（倒数第二个交易日选股 → 最后交易日验证；win_rate、MFE/MAE、对截面中位数）。限制：收盘对收盘、未扣成本。

## 5. 验证基础设施（KEEP）

- `quant/validation/purged_kfold.py` — purge/embargo 真实
- `quant/validation/walk_forward.py` — RankIC 折叠验证，阈值 mean IC≥0.015、ICIR≥0.20
- `quant/validation/overfitting.py` — walk_forward_splits、DSR、PBO
- `quant/validation/leakage_detector.py` — 含 survivorship 检查项
- ⚠️ `scripts/run_quantos_audit.py` L103 自述泄漏检查是合成桩 —— 该脚本结论 UNVERIFIED

## 6. 对照重构文档 §9 指标清单的缺口

| 类别 | 已有 | 缺 |
|---|---|---|
| Return | cumulative、win_rate | annualized、excess（真实 benchmark）、profit_factor、avg gain/loss |
| Risk | max_drawdown、sharpe | sortino、calmar、downside_deviation、tail_loss_95、worst_trade |
| Trading | turnover 部分、成本 | avg_holding_days、capacity、liquidity_hit_rate |
| Prediction | RankIC、ICIR | calibration_curve、precision/recall@k、confidence_vs_realized |
| Robustness | DSR、PBO、walk-forward | parameter_sensitivity、bootstrap_ci、regime_breakdown |

## 7. 数据窗口约束（必须如实输出）

仓库历史仅 **2025-12-15 ~ 2026-06-26（约 130 个交易日）**。重构文档的 2016/2022/2024 切分不可行。Phase 4 策略：

1. Phase 1 先回填 ≥2018 历史（Tushare）扩窗；
2. 无论窗口多长，所有报告输出真实日期范围；
3. 窗口不足以支撑结论时输出 `BLOCKED_BY_VALIDATION: insufficient_history`，禁止包装成推荐。
