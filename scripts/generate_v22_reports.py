"""Generate the v2.2 validation reports (§9, §12.4, §13) from live runs.

Runs real advisory calls against the warehouse (cold + warm) to measure cache
performance, then writes:
  docs/validation_reports/cache_performance_report.md
  docs/validation_reports/formula_explainability_report.md
  docs/validation_reports/data_freshness_report.md
  docs/validation_reports/advisory_sample_report.md
All numbers come from actual measured runs — nothing synthetic.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "validation_reports"

SAMPLE_SYMBOLS = ["600519.SH", "000001.SZ", "300750.SZ"]


def main() -> int:
    from quant.application.advisory_service import get_advisory_service
    from quant.cache_os.metrics import get_cache_metrics
    from quant.cache_os.policy import get_policy_registry
    from quant.scoring_os.weights import get_weight_set

    OUT.mkdir(parents=True, exist_ok=True)
    svc = get_advisory_service()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    timings = []
    cards = {}
    for sym in SAMPLE_SYMBOLS:
        t0 = time.perf_counter()
        cold = svc.advise(sym, capital_cny=20000, force_refresh=True)
        t_cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        warm = svc.advise(sym, capital_cny=20000)
        t_warm = time.perf_counter() - t0
        timings.append((sym, t_cold, t_warm, warm.get("headline", {}).get("cache_status")))
        cards[sym] = cold

    metrics = get_cache_metrics().snapshot()
    session = get_policy_registry().session_state()

    # ---- cache performance report ----
    lines = [
        "# Cache Performance Report (v2.2)", "",
        f"> 生成时间：{now} · 实测数据（非模拟） · session={session['session']}"
        f" · calendar_status={session['calendar_status']}", "",
        "## 单股建议：冷启动 vs 缓存命中", "",
        "| 股票 | 强制刷新（冷） | 缓存读取（热） | 加速比 | 热路径缓存状态 |",
        "|---|---:|---:|---:|---|",
    ]
    for sym, tc, tw, status in timings:
        speedup = tc / tw if tw > 0 else float("inf")
        lines.append(f"| {sym} | {tc:.2f}s | {tw:.3f}s | {speedup:.0f}× | {status} |")
    cs = metrics["cache_summary"]
    lines += [
        "",
        "## 缓存计数（本次进程累计）", "",
        f"- hit_rate: **{cs['hit_rate']:.2%}**（hit {cs['hit_count']} / miss {cs['miss_count']}）",
        f"- stale_allowed: {cs['stale_allowed_count']} · degraded: {cs['degraded_count']}"
        f" · unavailable: {cs['unavailable_count']} · force_refresh: {cs['force_refresh_count']}",
        "",
        "## 性能预算对照（v2.2 §4.3）", "",
        "| 指标 | 预算 | 实测 | 结论 |",
        "|---|---|---|---|",
        f"| single_stock_cached_analysis | ≤3s | {max(t[2] for t in timings):.3f}s | "
        f"{'PASS' if max(t[2] for t in timings) <= 3 else 'FAIL'} |",
        f"| single_stock_force_refresh | ≤15s | {max(t[1] for t in timings):.2f}s | "
        f"{'PASS' if max(t[1] for t in timings) <= 15 else 'FAIL'} |",
        "",
        "缓存分层：L0 内存 + L1 磁盘（advisory_result / feature_vector / kronos_prediction），",
        "键为 sha256(CacheKey)，底层 data_version 变化自动失效，无需手动清缓存。",
    ]
    (OUT / "cache_performance_report.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- formula explainability report ----
    ws = get_weight_set()
    sample = cards[SAMPLE_SYMBOLS[0]]
    bd = sample.get("panel_b_quant_computation", {})
    lines = [
        "# Formula Explainability Report (v2.2)", "",
        f"> 生成时间：{now} · 公式版本：**{ws['score_weight_version']}**", "",
        "## 总分公式", "",
        "```",
        "FinalScore = BaseOpportunityScore × RegimeMultiplier × DataQualityMultiplier",
        "             − RiskPenalty − ExecutionPenalty − OverheatPenalty",
        "```", "",
        "## 权重与理由", "",
        "| 因子 | 权重 | 理由 |", "|---|---:|---|",
    ]
    for k, w in ws["weights"].items():
        lines.append(f"| {ws['labels_zh'][k]} ({k}) | {w:.0%} | {ws['rationale_zh'][k]} |")
    lines += [
        "", f"## 实测样例：{sample.get('name', '')}（{SAMPLE_SYMBOLS[0]}）", "",
        "```",
        *bd.get("text_lines", []),
        "```", "",
        f"- 缺失因子（诚实降权，非编造）：{', '.join(bd.get('missing_factors') or []) or '无'}",
        "- 归一化：横截面分位数 + 5%/95% winsorize；缺失值记中性50并将该因子权重减半",
        "- 防过拟合：权重版本固定入库；调优仅允许 walk-forward / purged k-fold（§10），当前未调优",
    ]
    (OUT / "formula_explainability_report.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- data freshness report ----
    from quant.cache_os.policy import DEFAULT_POLICIES

    lines = [
        "# Data Freshness Report (v2.2)", "",
        f"> 生成时间：{now} · 交易时段判定：{session['session']}"
        f"（calendar_status={session['calendar_status']}——无交易日历表时按工作日近似并如实标注）", "",
        "## TTL 策略表（config/cache_policy.yaml）", "",
        "| 数据类型 | 交易时段 TTL | 非交易时段 TTL |", "|---|---:|---:|",
    ]
    for dtype, p in DEFAULT_POLICIES.items():
        if "ttl_seconds" in p:
            ttl = p["ttl_seconds"]
            lines.append(f"| {dtype} | {ttl if ttl else '参数哈希永久'} | 同左 |")
        else:
            lines.append(f"| {dtype} | {p.get('trading_ttl_seconds', '—')}s | {p.get('non_trading_ttl_seconds', '—')}s |")
    lines += [
        "", "## 新鲜度状态机", "",
        "fresh（可用于新推荐）→ stale_allowed（仅展示，标注）→ expired（仅历史回看）；",
        "degraded（主源失败降级，可用但标注）；unavailable（相关评分强制降权）。", "",
        "## 当前数据现状（实测）", "",
        f"- warehouse data_version: `{svc.cache_status()['warehouse_data_version']}`",
        "- 实时行情：本轮建议基于 EOD 收盘数据，前端标注「最新（EOD 收盘数据）」，不冒充实时",
        "- 资金流 / 舆情 / 政策源：仓库无合法可查来源 → 因子标记 missing 并降权（绝不编造）",
    ]
    (OUT / "data_freshness_report.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- advisory sample report ----
    lines = [
        "# Advisory Sample Report (v2.2)", "",
        f"> 生成时间：{now} · 全部输出来自真实仓库数据 + 固定公式；不构成投资建议，不承诺收益", "",
    ]
    for sym in SAMPLE_SYMBOLS:
        card = cards[sym]
        if card.get("blocked"):
            lines += [f"## {sym}", "", f"- 状态：无法生成（{card.get('blocker_reason')}）", ""]
            continue
        h = card["headline"]
        plan = card["panel_d_conditional_advice"]["trade_plan"]
        lines += [
            f"## {card.get('name', '')}（{sym}）", "",
            f"- 【推荐结论】{h['conclusion']}",
            f"- 【最重要理由】{'；'.join(h['top_reasons'])}",
            f"- 【最大风险】{'；'.join(h['top_risks'])}",
            f"- 【数据新鲜度】{h['data_freshness']} · 【缓存状态】{h['cache_status']}",
            f"- 【公式版本】{h['score_weight_version']} · 【更新时间】{h['updated_at']}",
            f"- 【置信度】{h.get('confidence')}（{h.get('confidence_band')}）",
            f"- 最终分：{card['panel_b_quant_computation']['final_score']} / 100",
        ]
        if plan.get("buy_zone"):
            lines += [
                f"- 买入区间：¥{plan['buy_zone'][0]} – ¥{plan['buy_zone'][1]} · 止损 ¥{plan['stop_loss']}"
                f" · 目标 ¥{plan['target_1']} / ¥{plan['target_2']} · 盈亏比 {plan['risk_reward_ratio']}",
            ]
        if plan.get("minimum_lot_warning"):
            lines.append(f"- ⚠️ {plan['minimum_lot_warning']}")
        dnb = card["panel_d_conditional_advice"].get("do_not_buy_conditions") or []
        if dnb:
            lines.append(f"- 禁买条件：{'；'.join(dnb)}")
        lines.append("")
    lines.append(f"---\n\n{cards[SAMPLE_SYMBOLS[0]].get('disclaimer', '')}")
    (OUT / "advisory_sample_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "reports": [str(p) for p in sorted(OUT.glob("*.md"))],
        "timings": [{"symbol": s, "cold_s": round(c, 2), "warm_s": round(w, 3)} for s, c, w, _ in timings],
        "hit_rate": cs["hit_rate"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
