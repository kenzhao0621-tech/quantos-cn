# MODEL_AUDIT — 模型审计

> 结论先行：筛选器是真实的多因子管线（KEEP）；LightGBM 集成层代码真实但**默认 degraded**（缺训练指标工件）；"持续学习"只是前向收益分析且**关键函数从未被调用**；Kronos 完全缺席；Qlib 基线的 Sharpe 是硬编码。

## 1. 筛选器因子层（KEEP）

`quant/application/screener_service.py`：

- 因子：`ret_20`、`ret_60`、`trend`（vs MA20）、`vol_20` 惩罚、`avg_amount` 流动性（PRESETS L27–32，SQL L283–306）
- 可交易性：流动性下限、剔除涨停（`pct_chg >= 9.8`）、主板过滤、价格/行业过滤（L315–330）
- 中性化：市值+行业 z-score（`_build_scoring_zmaps` L982–996 → `quant/features/neutralization.py`）
- 预设：momentum / trend / balanced / low_vol

评分管线：`assign_baseline_scores()` → `alpha158_lite_zscore`（**实为 5 因子 price_momentum_lite**，`quant/screener/alpha_blend.py` L1–44）→ `finalize_with_ensemble()`。

**问题**：命名误导（"Alpha158-lite" 有三个不同含义：158 列 ML 特征 / 5 因子混合 / qlib 4 列）；模型版本字符串三套并存（v4_industry_neutral / v5_ensemble_lgbm / v6_trading_agents_zh）。Phase 2 统一。

## 2. ML 集成层（真实代码，默认 degraded）

| 组件 | 状态 | 证据 |
|---|---|---|
| 训练脚本 | 真实（DuckDB + Alpha158 宽表，LambdaRank） | `scripts/train_lgbm_sample.py`（universe=`csi300_proxy_top300_liquid`，产出 model id `alpha158_lgbm_ranker_sample`） |
| 模型文件 | `models/latest_lgbm_ranker.pkl` 存在 | **UNVERIFIED**（无配套指标工件，无法复现训练） |
| 门控 | `get_ml_gate_status()`：需要 model 文件 + registry 非 REJECTED + `metrics.train.trained` + 泄漏报告 + RankIC≥0.015 + ICIR≥0.20 | `quant/models/ml_scorer.py` L54–75 |
| 现状 | `artifacts/model_metrics.json`、`artifacts/model_registry.json` **不存在** → 门控失败 → `baseline_fallback` | glob 为空 |
| 集成权重 | 45% ML + 35% baseline + 20% 风险惩罚 | `ml_scorer.py` L83、`ensemble.py` L17–37 |
| 降级诚实性 | ✅ `ml_active: false`、`ml_degraded_reason` 透出 API | `screener_service.py` L164–185 |

**处置**：门控/降级机制 KEEP（符合重构文档的 degraded 原则）；Phase 5 用真实训练跑通门控并落 metrics/registry 工件。

## 3. "持续学习"（PATCH — 未接线）

`quant/learning/outcome_tracker.py`：

- `record_screener_run()` **定义但全仓无调用** —— 学习台账从未写入。
- `compute_learning_summary()` 从 DuckDB 算 T+1 前向收益 —— 被 operations/platform_health 使用，真实。
- `gateway/learning/screener_learning.py` 的"学习循环" = `prove_next_day()` + 启发式预设建议，**不是模型再训练**。

**处置**：Phase 5/6 把 `record_screener_run` 接入 `screener/run` 端点；把学习循环产出接入 ResearchOS 参数搜索。

## 4. 验证声明的真实性

| 声明 | 真伪 |
|---|---|
| `purged_kfold_passed` | ✅ 真实计算（`model_validation_service._persist_validation()` L321–337），但**需运维手动触发** `/api/v1/models/validate`；不跑则 `validation_status: NOT_RUN` |
| `model_uncertainty` | ❌ 启发式公式 `0.35 + vol/8 + disclosure bump`（`enrichment.py` L75, L123），非校准不确定度 —— Phase 3 用 Kronos 分布或 conformal 校准替换/如实改名 |
| 预期收益区间 | ⚠️ 依赖 `artifacts/score_bucket_stats.json` 历史分桶；缺失时 INSUFFICIENT_HISTORY（诚实） |
| Qlib 基线 sharpe | ❌ 硬编码 0.5（`integrations/qlib/workflow.py` L33–34）—— REWRITE |

## 5. Kronos（不存在 → Phase 3 全新增）

- 全仓 grep 无 kronos 命中。
- 环境约束：主 venv Python 3.9.6（Kronos 需 ≥3.10），无 torch。本机有 python3.12（Homebrew）、M3 Pro 18GB —— 按重构文档策略归类为 "Apple Silicon" 档：**Kronos-mini 默认 + Kronos-small 可选**。
- 设计决策：独立 `.venv-kronos`（python3.12 + torch CPU/MPS + huggingface_hub），主进程经子进程 JSON I/O 调用（与既有 `gateway/native/bridge.py` 模式一致）。安装/下载失败 → `KronosSignalProvider` 返回 `degraded: true` + 统计学降级路径（历史收益 bootstrap 分布），全链路标注。

## 6. 基线模型对照重构文档 §8

| 要求 | 现状 |
|---|---|
| Buy&Hold / benchmark | ❌ 回测 benchmark 为假（见 BACKTEST_AUDIT） |
| MA crossover / Momentum / MeanRev / VolBreakout | ⚠️ `quant/models/baseline.py` 有部分动量基线；Phase 5 补全 |
| Ridge/Lasso | ✅ Ridge 降级路径已有 |
| RF / XGBoost/LightGBM | ✅ LightGBM 已有；RF 可选 |
| MLP/LSTM/GRU/TCN | ❌ 无 torch —— 列为可选（sidecar venv 就绪后 Phase 5 酌情，不作为门槛） |
| Kronos-mini | ❌ Phase 3 |
| Alpha158 因子集 | ✅ `quant/features/alpha158.py` |
