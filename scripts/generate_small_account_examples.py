"""Generate docs/user_advisory_examples/small_account_*_example.md (v2.2 §13)
from real advisory runs at 5000 / 10000 / 20000 CNY. Honest outputs only —
if nothing is affordable or scores are weak, the example says so."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "user_advisory_examples"
CAPITALS = [5000, 10000, 20000]
# Liquid mainboard names across price ranges so lot-size effects are visible.
CANDIDATES = ["000001.SZ", "601318.SH", "600036.SH", "000333.SZ", "600519.SH"]


def main() -> int:
    from quant.application.advisory_service import get_advisory_service

    svc = get_advisory_service()
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for capital in CAPITALS:
        lines = [
            f"# 小资金示例：账户 {capital} 元（v2.2）", "",
            f"> 生成时间：{now} · 数据：真实 Tushare EOD 仓库 · 公式版本 v2.2_default_conservative_ashare",
            "> 仅研究/模拟交易示例，不构成投资建议，不承诺收益。", "",
        ]
        buyable = 0
        for sym in CANDIDATES:
            card = svc.advise(sym, capital_cny=float(capital), position_weight=0.5)
            if card.get("blocked"):
                lines += [f"## {sym}", "", f"- 无法分析：{card.get('blocker_reason')}", ""]
                continue
            h = card["headline"]
            plan = card["panel_d_conditional_advice"]["trade_plan"]
            shares = plan.get("shares") or 0
            cost = plan.get("position_size_rmb") or 0
            lines += [
                f"## {card.get('name', '')}（{sym}）", "",
                f"- 结论：{h['conclusion']} · 最终分 {card['panel_b_quant_computation']['final_score']}"
                f" · 置信度 {h.get('confidence')}（{h.get('confidence_band')}）",
            ]
            if shares > 0 and plan.get("buy_zone"):
                buyable += 1
                stop, t1 = plan["stop_loss"], plan["target_1"]
                entry = (plan["buy_zone"][0] + plan["buy_zone"][1]) / 2
                lines += [
                    f"- 可买 {shares} 股（{shares // 100} 手），约 {cost:.0f} 元，剩余现金约 {capital - cost:.0f} 元",
                    f"- 买入区间 ¥{plan['buy_zone'][0]}–¥{plan['buy_zone'][1]} · 止损 ¥{stop} · 目标1 ¥{t1}",
                    f"- 跌到止损约亏 {(entry - stop) * shares:.0f} 元；涨到目标1约赚 {(t1 - entry) * shares:.0f} 元",
                    f"- 明天高开>5%：不追，等回落到区间内；明天低开：仅在区间内且未破止损时按计划执行",
                ]
            else:
                warn = plan.get("minimum_lot_warning") or (plan.get("do_not_buy_conditions") or ["无可执行方案"])[0]
                lines.append(f"- 本资金不可执行：{warn}")
            lines.append("")
        if buyable == 0:
            lines += ["## 结论", "", "当前样本内没有满足「买得起一手 + 结构成立 + 分数达标」的标的 —— **空仓等待也是建议**。", ""]
        (OUT / f"small_account_{capital}_example.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"written small_account_{capital}_example.md (buyable={buyable})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
