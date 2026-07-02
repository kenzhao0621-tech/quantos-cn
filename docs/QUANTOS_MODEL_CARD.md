# QuantOS 2.0 模型卡（Model Card）

> 更新：2026-07-02 · 分支 `feat/quantos-kronos-agents-refactor`
> 定位：**A 股金融时序预测与投资建议研究系统** —— 仅供研究与辅助决策，不构成投资建议，不承诺收益。默认仅 paper trading。

## 1. 信号来源与融合

最终建议由多信号融合产生，**任何单一模型（包括 Kronos）都不能单独决定买卖**：

| 信号 | 实现 | 状态 |
|---|---|---|
| Kronos-mini 分布预测 | `quant/models/kronos/`（sidecar 推理，30 条 Monte Carlo 路径 → expected_return/volatility/downside_risk/confidence） | 真实推理（Apple MPS，~13s/股）；不可用时 bootstrap 统计降级，confidence 封顶 0.35 且必标 `degraded` |
| 多因子排序 | `quant/application/screener_service.py`（动量20/60、趋势、波动惩罚、流动性，市值+行业中性化） | 真实 |
| price_momentum_lite 混合 | `quant/screener/alpha_blend.py`（5 因子，**非完整 Alpha158**，命名已澄清） | 真实 |
| LightGBM LambdaRank | `quant/models/lgbm_ranker.py` + `ml_scorer.py` 门控 | 代码真实；**门控默认 degraded**（需先跑训练产出 metrics/registry 工件），降级原因透出 API |
| 市场状态 | `quant/features/market_regime.py`（沪深300 趋势/波动 regime） | 真实 |
| 多智能体共识 | `gateway/agents/quantos/`（9 角色确定性规则引擎，JSON I/O） | 真实规则（非 LLM 编造；engine 字段标注 `deterministic_rules_v1`） |

融合权重见 `configs/quantos.quick.yaml` `signals.weights`，可配置、可被参数搜索覆盖。

## 2. Kronos 模型详情

- 模型：`NeoQuasar/Kronos-mini`（4.1M 参数，2048 token 上下文，K 线专用 tokenizer）；可选 `Kronos-small`（24.7M）
- 运行环境：独立 `.venv-kronos`（Python 3.12 + torch MPS）——主环境 Python 3.9 与 Kronos 要求（≥3.10）不兼容，经 JSON 子进程调用
- **默认禁止训练**，只做推理与信号融合；预测输出为分布（路径/置信区间），不是单点"必涨/必跌"
- 输入：前复权 OHLCV（复权因子覆盖 ≥90% 时启用，否则用未复权并标注 `price_adjusted: false`）

## 3. 训练/验证数据

- 数据仓库：DuckDB + Parquet 分区，Tushare 日线（回填至 2018-04，约 1369 个交易日、690 万行）、BaoStock 指数、AKShare 实时
- 已知缺陷（如实声明）：复权因子回填仍在进行中；股票池尚未按历史时点构建（幸存者偏差 PARTIAL，见 `quant/validation/leakage_detector.py`）

## 4. 验证与门槛

- Purged K-Fold + embargo、walk-forward、DSR、PBO（真实参数变体）、RankIC —— `quant/validation/`
- §9.3 验证门（`quant/validation/gate.py`）：OOS Sharpe ≥0.8、回撤 ≥-15%、跑赢沪深300、扣成本、A 股约束齐备，任一不满足 → `BLOCKED_BY_VALIDATION`，不会包装成推荐
- 实测示例（2026-07-02 quick 回测，40 信号日）：筛选器组合 Sharpe -0.15、净收益 -0.94% vs 沪深300 +2.58% → **如实判 BLOCKED**

## 5. 已知局限

1. 验证窗口受数据回填进度限制；窗口不足时输出 `insufficient_history` 并 BLOCKED。
2. 情绪信号仅覆盖官方披露源（非全网舆情），SentimentAgent 无数据时如实降级。
3. 涨跌停模拟为收盘近似（次日开盘跳空 ≥9.7% 判不可买），非盘中撮合。
4. LLM 智能体为可选路径，默认确定性规则引擎。
5. 模型可能在市场结构变化（regime shift）时失效——每个建议附失效条件。
