# Skill Routing (Project)

See also: `docs/cursor-skills/05_SKILL_ROUTING.md`

## Superpowers sub-skills (do not duplicate)

| Sub-skill | Stage |
|-----------|-------|
| brainstorming | Ideation |
| context-pack | One-shot context |
| writing-plans | Implementation plan |
| planning-with-files | Long-running state |
| executing-plans / subagent-driven-development | Execute |
| test-driven-development | TDD |
| systematic-debugging | Debug (debug-radar routes here) |
| requesting-code-review / receiving-code-review | Review (code-review routes here) |
| verification-before-completion | Verify (ship-checklist routes here) |

## Disabled by default

- **ralph-loop** — requires explicit authorization + max_iterations

## BLOCKED execution

- **agent-reach** — install definition only; needs CLI + credentials

## Release & deps

| Task | PRIMARY |
|------|---------|
| Changelog / release notes | release-docs |
| Pre-install dep scan | ci-fixer + npm audit; FALLBACK dependency-guard |

## Research (Phase 3)

paper-intake → paper-structure-analyzer → section-by-section-reader → figure-table-extractor → citation-graph-builder → research-synthesis → research-integrity-guard

document-intake → markitdown (`.venv-markitdown/bin/markitdown`) → document-conversion-qa

## Refactor

repo-cartographer → refactor-lens (FALLBACK) → code-simplifier

## OS routers (Phase 1)

| Task | PRIMARY |
|------|---------|
| Classify image input | image-analysis-router |
| Sanitize web fetch | web-content-safety-gate |
| Licensed stock photos | licensed-media-finder |
| Architecture diagrams | diagram-architect → mermaid-renderer |
| Visual screenshot QA | webapp-testing → Playwright → screenshot-qa |

See `docs/cursor-operating-system/06_SKILL_ROUTING.md`.

## China A-share daily outlook (PAPER_TRADING_ONLY)

| Task | PRIMARY |
|------|---------|
| A股、大盘、板块、今日买什么、盘前简报 | **china-a-share-daily-trading-outlook** |
| T+1 / 涨跌停 / 停牌规则 | china-market-rules-engine |
| 数据时效 / 交易日历 | china-quant-data-quality-guard |
| 公开数据拉取 / 新闻研究 | china-a-share-quant-research → web-content-safety-gate |
| 100分制评分 | china-a-share-factor-lab |
| 止损止盈仓位 | china-equity-risk-model |
| 公告催化 | china-a-share-event-study → research-integrity-guard |
| 回测（仅用户请求） | china-a-share-backtest-engine |
| 个股档案 | china-a-share-stock-dossier |
| 板块轮动 | china-a-share-sector-rotation |
| 机构动向 | china-a-share-institutional-flow |
| 政策监控 | china-a-share-policy-monitor |
| 组合模拟 | china-a-share-portfolio-simulator |

CLI: `python3 tools/china_quant/cli.py premarket --fixture universe_full`

**Do NOT** use trading-agents (QUARANTINE) or agent-reach xueqiu for quant pipeline.

## PRIMARY quick reference

| Task | PRIMARY |
|------|---------|
| Find skills | find-skills |
| Design research | ui-ux-pro-max |
| Build UI | frontend-design |
| Polish UI | impeccable |
| E2E test | webapp-testing |
| CI fix | ci-fixer |
| Simplify code | code-simplifier |
| Repo map | repo-cartographer |
| MCP server | mcp-builder |
| Create skill | create-skill (built-in) |
