# DATA_SOURCE_AUDIT — 数据源审计

> 结论先行：实时行情走 AKShare（sina 主 / eastmoney·split 备），EOD 走 Tushare（日线）+ BaoStock（指数），存储为 Parquet 分区 + DuckDB 视图。数据是真实的；主要问题是**历史深度不足、未复权、ST 标记造假、部分提供方是空壳**。

## 1. 提供方清单与状态

| 提供方 | 文件 | 数据集 | 状态 |
|---|---|---|---|
| akshare_sina | `quant/providers/akshare_family.py` L114–287 | 实时全市场 spot（`ak.stock_zh_a_spot()`）、指数 | **KEEP** — 实时主路径（`live_market_service.py` L107–114 硬指定） |
| akshare_eastmoney / akshare_split | 同上 L110–111, L290–383 | spot 分交易所备用 | KEEP — 路由备用 |
| tushare | `quant/providers/tushare_provider.py` | daily_bars、trade_cal、stock_basic、index_daily、daily_basic | **KEEP+PATCH** — EOD 主源；`list_status="L"` 只取存续股（幸存者偏差）；适配器 `is_st: False` 硬编码 |
| baostock | `quant/providers/baostock_provider.py` | 指数、日线、日历 | KEEP — `adjustflag="3"`（未复权，已诚实标注 `adjustment_mode: raw`） |
| manual_snapshot | `quant/providers/manual_snapshot.py` | 手动导入 | KEEP — `freshness=MANUAL_IMPORT`，`require_live` 会拒绝 |
| rqdata / jqdata / qmt / supermind | `quant/providers/*.py` | — | **DEPRECATE** — 空壳/恒 SKIPPED（详见 REMOVE_OR_REWRITE_LIST） |
| authorized_web / official_file | 同目录 | 披露/文件导入 | KEEP |
| Yahoo | — | — | 不存在（无需处理） |
| Qlib | `integrations/qlib/provider.py` | 只读 DuckDB 适配 | KEEP — 非独立数据源 |

## 2. 数据路由与门控

- **V2 主路径** `quant/market_data_fabric.py`：provider 链（`routing_v2.yaml`）→ freshness 门（L158–164）→ DQ 门（L166–178）→ `require_live` 拒绝 manual/fixture/非实时（L180–184）→ 跨源 quarantine（L196–201）。**设计良好，KEEP。**
- **V1 并行路径** `quant/composite_provider.py`：只有 DQ 门、无 freshness 门，被 CLI `fetch-market-snapshot` 和日报管线使用。**风险：绕过 freshness 检查。处置：合并进 Fabric（Phase 1）。**

## 3. 存储层实测（2026-07-02）

| 存储 | 内容 | 实测 |
|---|---|---|
| `data/warehouse/quant.duckdb` | daily_bars / index_bars / features / disclosures 四个视图 | 69.6 万 / 2.0 千 / 66.1 万 / 60 行 |
| `data/historical/daily_bars/` | year/month/date 分区 Parquet | **仅 2025-12-15 起（~6.5 个月）** |
| `data/sectors/*.json`、`data/fundamentals/*.json` | 行业/基本面 JSON 侧车 | **不在 DuckDB 视图内**（fundamentals 截断 5000 行） |
| `data/gateway/*.json` | live_snapshot、broker_config、kill_switch、runs 等运行态 | 正常 |

## 4. 与重构文档 5.2 标准表结构的差距

| 目标表 | 现状 | 缺口 |
|---|---|---|
| market_daily（含 vwap/adj_factor/paused/limit_up/limit_down/is_st/source/updated_at） | daily_bars 只有 OHLCV+pct_chg+amount | **缺 adj_factor、paused、limit_up/down、is_st、vwap**；Phase 1 补列 |
| fundamental | JSON 侧车（daily_basic 子集） | 未入仓、缺 revenue/net_profit/roe 等利润表字段 |
| news_sentiment | 无（仅 disclosures 60 行） | Phase 1 最小实现：披露→情绪占位（degraded 标注）或明确缺席 |
| index_daily | index_bars 存在 | 日期格式混杂（20250205 与 2026-06-17 并存），需归一 |
| industry_map | sectors JSON | 未入仓，Phase 1 建视图 |

## 5. A 股真实性约束现状

| 约束 | 现状 | 证据 |
|---|---|---|
| T+1 | ✅ 纸上引擎强制（`T_PLUS_1_SELLABLE_INSUFFICIENT`、`settle_t_plus_1()`） | `gateway/paper/engine.py` L254–257, L327 |
| 涨跌停 | ⚠️ 扁平 ±9.8%，科创 20%/北交 30%/ST 5% 仅 `tools/china_quant/rules.py` LIMIT_PCT 有表未接入主流程 | `quant/tradability/mask.py` L47–50 |
| 停牌 | ⚠️ 纸上引擎有参数，但日线回填无系统性停牌标记（靠流动性推断） | `paper/engine.py` L220–224 |
| ST | ❌ **Tushare 适配器全量 `is_st: False`**（L51）；仅 AKShare spot / Sina 按名称推断 | `tushare_daily_adapter.py` |
| 复权 | ❌ 仓库全程未复权；`corporate_action_checker.py` 已诚实标注 `unadjusted_close` | `quant/dataos/corporate_action_checker.py` L22–33 |
| 交易日历 | ✅ Tushare trade_cal + AKShare + BaoStock 三源 | `tushare_provider.py` L162–170 |
| 幸存者偏差 | ⚠️ `security_master` 只取 `list_status="L"`；`bias_guards.py`、`leakage_detector.py` 有检查项但股票池非按历史日期构建 | `tushare_provider.py` L172 |

## 6. 新鲜度诚实性

- ✅ EOD 恒标 `END_OF_DAY`（`market_data_service.py` L178）；Tushare spot 标 `not_intraday_realtime: True`。
- ✅ 实时缓存回落显式标 `stale_fallback: True`（`live_market_service.py` L233–243），前端有"缓存回落"标签。
- ❌ **漏洞**：`gateway/market_status.py` `_live_status()` L58–91 只看行数>100，不检查 `stale_fallback` —— 陈旧快照可显示"实时 OK"。**Phase 1 必修。**
- ✅ `gateway/data_gate.py` 开市时段 stale → `LIVE_SNAPSHOT_STALE` 阻断交易路径。

## 7. Mock/Fixture 污染风险

- fixture 全部显式标注（`DataFreshness.FIXTURE`），且 `data_quality.py` L61–64、`freshness_contract.py` L131–132、`candidate_data_gate.py` L33–41 三层拒绝。
- 残余风险：`tools/china_quant run-daily --fixture` 可产出面向用户的 markdown 日报（有 FIXTURE 横幅但仍在 `docs/ai/`）——Phase 1 将 fixture 输出改道至 `artifacts/test/`。
- 生产代码（quant/gateway）无 `np.random` 命中；合成数据仅测试脚本。

## 8. Phase 1 数据整改清单（优先级序）

1. `market_status._live_status()` 检查 `stale_fallback`，禁止陈旧快照显示"实时 OK"。
2. Tushare 适配器修复 ST 标记（用 name 或 namechange 接口），补 paused/limit 标记列。
3. 回填历史至 ≥2018（Tushare daily 按年分批），扩充 ValidationOS 可用窗口。
4. 增加 adj_factor 管线（Tushare `adj_factor` 接口），features/回测切换后复权。
5. `sync-all` 扩展到 sectors/fundamentals/disclosures，或 UI 改名"同步核心数据"。
6. sectors/fundamentals 入 DuckDB 视图（industry_map / fundamental）。
7. index_bars 日期格式归一。
8. 合并 CompositeMarketDataProvider → MarketDataFabric。
