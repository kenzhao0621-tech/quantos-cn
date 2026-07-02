# QuantOS 2.0 数据质量报告（Data Quality Report）

> 生成：2026-07-02 · 来源：`scripts/check_data_quality.py`（`artifacts/reports/data_quality_*.json`）

## 1. 仓库现状（真实盘点）

| 数据集 | 行数 | 窗口 | 来源 | 状态 |
|---|---|---|---|---|
| daily_bars | ~690 万 | **2018-04 ~ 2026-07**（回填后约 1369 个交易日；2021-08~2023-11 区间仍在补） | Tushare pro.daily | ✅（未复权，见 §3） |
| index_bars | ~2,000 | 2025-02 ~ 2026-06 | BaoStock | ✅ |
| features | ~66 万 | 2025-12 ~ 2026-06 | Alpha158 兼容宽表 | ✅ |
| industry_map | 5,529 | 当前快照 | Tushare stock_basic | ✅（新视图） |
| fundamental | 5,000 | 最近交易日 | Tushare daily_basic | ✅（新视图；截断 5000 行） |
| adj_factors | 回填中 | — | Tushare adj_factor | ⚠️ **degraded**（限流，检查点续跑） |
| trade_calendar | 3,105（2,060 开市日） | 2018 ~ 2026 | BaoStock | ✅（新视图） |
| disclosures | 60 | — | 官方披露 | ✅（覆盖有限） |

质量检查全部通过：无缺失值、无重复、无异常价格/成交量、极端涨跌幅在阈值内、时间序有序、新鲜度达标（verdict=OK，adj_factors 覆盖不足时报 WARN）。

## 2. 本次重构修复的数据真实性问题

1. **ST 标记造假**：Tushare 适配器原先对全部股票硬编码 `is_st: False`；现从本地证券主档名称推断（覆盖 232 只 ST），无法确认时输出 `null`（未知）而非假 False。
2. **陈旧数据冒充实时**：`market_status` 原先只看行数即显示"实时 OK"；现检查 `stale_fallback` 与快照年龄（>1h 判过期），过期显示"实时已过期 + 最后更新时间"。
3. **板块差异化涨跌停**：原先全市场扁平 ±9.8%；现主板 10% / ST 5% / 科创创业 20% / 北交 30%。
4. **停牌/涨跌停派生列**：日线行现带 `paused`、`at_limit_up/down`、`limit_pct`。
5. **行业/基本面入仓**：原先只存 JSON 侧车，现有 `industry_map` / `fundamental` DuckDB 视图，sectors API 不再恒返回空。
6. **前复权管线**：新增 `adj_factors` 回填 + `daily_bars_adj` 视图（覆盖 ≥90% 才启用，避免半套复权污染因子）。
7. **交易时段**：API 原先硬编码 `session: CLOSED`；现按真实 A 股时段（含午休/集合竞价）判定。

## 3. 仍然存在的已知缺陷（如实声明）

- **复权因子覆盖不完整**：Tushare adj_factor 接口限流严重，回填以检查点方式持续进行；覆盖不足期间特征/回测使用未复权价并在输出中标注 `price_adjusted: false`。除权除息日附近的动量因子有失真风险。
- **幸存者偏差 PARTIAL**：股票池来自当前存续股票（`list_status="L"`），未按历史时点重建；已退市股票不在回测池中，长窗口结果偏乐观。
- **历史缺口**：2021-08 ~ 2023-11 区间回填中；ResearchOS 面板有连续性守卫（跨缺口 >20 天自动截断），不会把缺口两端拼成一天收益。
- **披露覆盖有限**（60 条），SentimentAgent 在无披露时如实降级。

## 4. 复现

```bash
python scripts/check_data_quality.py --mode quick
python -m quant update-daily-bars --target-days 2000 --max-new 1500   # 历史回填（可重入）
python -m quant update-adj-factors --target-days 130 --max-new 200    # 复权因子（可重入）
```
