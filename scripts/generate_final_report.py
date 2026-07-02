#!/usr/bin/env python
"""Generate docs/QUANTOS_KRONOS_REFACTOR_REPORT.md from real artifacts + git log."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _latest_json(pattern: str, base: Path) -> dict | None:
    files = sorted(base.glob(pattern))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    now = datetime.now()
    git_log = subprocess.run(
        ["git", "log", "--oneline", "main..HEAD" if _branch_has_main() else "-12"],
        cwd=str(ROOT), capture_output=True, text=True,
    ).stdout.strip() or subprocess.run(
        ["git", "log", "--oneline", "-12"], cwd=str(ROOT), capture_output=True, text=True,
    ).stdout.strip()

    e2e = _latest_json("e2e_pipeline_*.json", ROOT / "artifacts" / "reports") or {}
    dq = _latest_json("data_quality_*.json", ROOT / "artifacts" / "reports") or {}
    kr = _latest_json("kronos_smoke_*.json", ROOT / "artifacts" / "reports") or {}
    bt = _latest_json("backtest_*.json", ROOT / "artifacts" / "backtests") or {}
    rs = _latest_json("research_*.json", ROOT / "artifacts" / "research") or {}

    stages = "\n".join(
        f"| {s.get('stage')} | {'✅' if s.get('ok') else '❌'} | {s.get('elapsed_sec', '—')}s |"
        for s in e2e.get("stages", [])
    ) or "| （尚未运行 e2e） | — | — |"

    kron_pred = kr.get("prediction", {})
    search = rs.get("search", {})
    gate = bt.get("validation_gate", {})

    doc = f"""# QuantOS × Kronos × TradingAgents-CN 重构总报告

> 生成：{now.isoformat(timespec='seconds')} · 分支 `feat/quantos-kronos-agents-refactor` · 由 `scripts/generate_final_report.py` 从真实工件汇编
> 定位：A 股金融时序预测与投资建议**研究**系统 —— 不构成投资建议，不承诺收益，默认仅 paper trading。

## 1. 端到端验收结果（最近一次真实运行）

模式：{e2e.get('mode', '—')} · paper_only={e2e.get('paper_only')} · 总体 {'✅ 通过' if e2e.get('ok') else '❌ 未通过'}（{e2e.get('generated_at', '—')}）

| 阶段 | 状态 | 耗时 |
|---|---|---|
{stages}

## 2. 各 OS 层交付状态

| 层 | 交付 | 真实性状态 |
|---|---|---|
| DataOS | ST/停牌/涨跌停标记、industry_map/fundamental/adj_factors/trade_calendar 视图、stale 诚实门、历史回填至 2018、质量门脚本 | 真实；adj_factors 回填中标 degraded |
| FeatureOS | 版本字符串统一（v7）、market_regime 特征、真实未来函数检测门 | 真实（verdict={dq.get('verdict', '—')}） |
| KronosOS | Kronos-mini sidecar（py3.12+MPS）、KronosSignalProvider 分布预测+信号、bootstrap 降级 | {'真实推理' if not kron_pred.get('degraded') else 'degraded: ' + str(kron_pred.get('reason'))} |
| ValidationOS | 真实沪深300基准（删除伪基准）、§9.2 全量指标、§9.3 验证门、跌停/停牌处理 | 真实（最近回测 gate={gate.get('verdict', '—')}） |
| ResearchOS | 面板引擎、6 基线、随机搜索、参数敏感性、真实变体 PBO、学习闭环接线 | 真实（eligible={search.get('eligible_count', '—')} / blocked={search.get('blocked_count', '—')}，PBO={((search.get('pbo_real_variants') or {}).get('pbo', '—'))}） |
| AgentsOS | 9 角色 JSON I/O、RiskManager 否决、A/B/C/D/BLOCKED、失效条件 | 真实规则引擎（deterministic_rules_v1） |
| ReportOS/UserOS | Markdown 研究报告（degraded 汇总强制）、研究报告/风险中心导航恢复、回测收益/回撤曲线、个股多智能体研究页 | 真实 |
| OpsOS | e2e 管线、三档配置（quick/standard/strict）、检查点回填 | 真实 |

## 3. 关键诚实性修复（重构前 → 重构后）

1. 回测基准 `total_ret*0.6` 伪造 → 真实沪深300/等权基准（防回归测试锁定）。
2. 事件回测收益硬编码 1% → 从真实 bar 序列解析，无法解析则 BLOCKED。
3. Tushare 全量 `is_st: False` → 证券主档推断，未知输出 null。
4. 陈旧行情可显示"实时 OK" → stale_fallback/超龄必显"实时已过期"。
5. Qlib 基线 sharpe 硬编码 0.5 → 真实面板计算或标 UNAVAILABLE_degraded。
6. `record_screener_run` 学习闭环从未接线 → screener/run 端点已接。
7. `session: CLOSED` 硬编码 → 真实 A 股交易时段。
8. Agent invoke 桩 → 真实 9 角色分析端点 `/api/v1/agents/analyze`。

## 4. 硬性边界（不变量）

- `PAPER_TRADING_ONLY=True` / `REAL_MONEY_EXECUTION_DISABLED=True`（模块常量）
- 实盘仅"工单 + 人工券商确认"（MANUAL_CONFIRM_ONLY），无直连下单
- 全仓禁用收益承诺措辞（测试锁定）
- 任何降级必标 `degraded` 并进入报告"真实性与降级状态汇总"

## 5. 提交记录

```
{git_log}
```

## 6. 交付物索引

- 审计：`docs/refactor_audit/`（9 份）
- 模型卡：`docs/QUANTOS_MODEL_CARD.md` · 风险披露：`docs/QUANTOS_RISK_DISCLOSURE.md`
- 回测：`docs/QUANTOS_BACKTEST_REPORT.md` · 数据质量：`docs/QUANTOS_DATA_QUALITY_REPORT.md` · 智能体：`docs/QUANTOS_AGENT_REPORT.md`
- 配置：`configs/quantos.{{quick,standard,strict}}.yaml`
- 工件：`artifacts/{{backtests,research,reports,agents}}/`

## 7. 下一步建议

1. 等待 adj_factors 与 2021-2023 历史回填完成后重算 Alpha158 特征并重跑验证（复权后动量因子更可信）。
2. 引入历史时点股票池（Tushare namechange/delist）消除幸存者偏差 PARTIAL。
3. 训练并落盘 LightGBM metrics/registry 工件，使 ML 门控从 degraded 转真实启用。
4. 可选接入 LLM 引擎替换规则 agent（保持 JSON 契约与 engine 标注）。
5. 扩充披露/舆情源提升 SentimentAgent 覆盖。

> 免责声明：本报告全部数字来自本地真实运行工件；历史结果不代表未来收益；仅供研究与辅助决策，不构成投资建议。
"""
    out = ROOT / "docs" / "QUANTOS_KRONOS_REFACTOR_REPORT.md"
    out.write_text(doc, encoding="utf-8")
    print(f"written: {out.relative_to(ROOT)}")
    return 0


def _branch_has_main() -> bool:
    r = subprocess.run(["git", "rev-parse", "--verify", "main"], cwd=str(ROOT), capture_output=True)
    return r.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
