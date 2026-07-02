# CONFLICT_RISK_REPORT — 合并冲突风险

## 高风险（不可直接覆盖）

| 风险 | 文件 | 说明 |
|---|---|---|
| **删除 Kronos** | B 删除了 `quant/models/kronos/*` | 直接 merge 会丢失 Phase 3 真实推理 |
| **删除 Agents** | B 删除了 `gateway/agents/quantos/*` | 直接 merge 会丢失 Phase 6 九角色管线 |
| **回退 benchmark** | B 的 `screener_backtest.py` 可能回退到假 benchmark | 必须保留 A 版本 |
| **删除 validation gate** | B 删除了 `quant/validation/gate.py` | 必须保留 A 版本 |
| **删除 e2e 脚本** | B 删除了 `scripts/e2e_quantos_pipeline.py` | 必须保留 A 版本 |
| **版本字符串** | A 统一 v7，B 无 version.py | 保留 A |

## 中风险（需手工合并）

| 风险 | 文件 | 策略 |
|---|---|---|
| 双 Advisory 入口 | `advisory_service.py` vs `screener_service` + agents | 统一走 AdvisoryOS，screener 保持独立 |
| 双评分路径 | `scoring_helpers.py` vs `scoring_os/formulas.py` | screener 用旧路径，advisory 用 ScoringOS v2.3 |
| 前端 UI 冲突 | `app.js` 两边都改 | 合并：保留研究报告+风险中心+scoring card |
| enrichment 冲突 | `quant/scoring/enrichment.py` | 保留 A 逻辑，advisory 不依赖 enrichment |

## 低风险（可直接迁入）

- `quant/cache_os/` 全新目录，无冲突
- `quant/compute_os/` 全新目录
- `quant/scoring_os/` 全新目录
- `quant/explain_os/` 全新目录
- `config/cache_policy.yaml`、`config/score_weights.yaml` 全新
- `tests/cacheos/`、`tests/computeos/`、`tests/scoringos/`、`tests/explainos/`、`tests/advisory/` 全新

## stub / degraded 清单（合并后必须标注）

| 项 | 分支 | 状态 |
|---|---|---|
| Kronos 推理 | A | 真实（sidecar），B 无 |
| 资金流/情绪/政策 | B | degraded/missing，不得伪造 |
| 交易日历 | A | 真实 BaoStock 3105 行；B 用 weekday 近似 |
| 复权因子 | A | 检查点续跑中，部分日期 degraded |
| 2021–2023 历史 | A | 回填进行中 |
| Agents evidence | A | 规则引擎，非 LLM；需 source_url |
| 北向实时资金 | 两分支均无 | 必须标 `realtime_northbound_available: false` |
