# FINAL_DAILY_REPORT_DEPLOYMENT

Repository: netlify-demo
Branch: chore/cursor-operating-system
Pre-change commit: bb88001
New local commit: TBD
Backup: .cursor-backups/quant-master-readiness-20260616-193503

## 修复失败测试
- Deterministic suite recovery passed: True
- Resolved failures: 0

## 仍有哪些失败
- disclosures: 0 rows

## 数据覆盖
- 指数覆盖: available=6
- 历史覆盖: partitions=120
- 行业覆盖(行业/申万): sector_rows=5529
- 财务覆盖: fundamentals_rows=5513
- 公告覆盖: disclosures_rows=0

## 实时 Provider
- spot provider=akshare_sina freshness=END_OF_DAY

## RAG / Memory
- Memory root: memory
- DuckDB: data/warehouse/quant.duckdb
- Token budget: max_total_context_tokens=5000

## 日报结果
- Decision: BLOCKED_BY_DATA
- no_trade_reasons: ['disclosures: 0 disclosure rows']
- daily_report.md: docs/ai/daily-trading/daily/2026-06-16_DAILY_QUANT_REPORT.md

## 明日盘中实时性测试（one-shot）
- Target: 2026-06-16T20:32:58.564354+08:00
- Installed: True
- Plist: config/launchd/com.netlify-demo.quant.live-market-hours-test.plist

## 下一步（纸面日报调度）
- status: NOT_SCHEDULED
- reason: blocked_by_data

## Mature / Rollback
- maturity: PIPELINE_VERIFIED_WITH_DATA_GAPS
- rollback guide: docs/cursor-operating-system/20_ROLLBACK_GUIDE.md
