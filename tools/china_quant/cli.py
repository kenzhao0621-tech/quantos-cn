#!/usr/bin/env python3
"""CLI for China A-share daily outlook (paper trading only)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.china_quant.data import fetch_live_snapshot, load_fixture, snapshot_from_fixture
from tools.china_quant.freshness import assess_freshness
from tools.china_quant.ledger import LedgerRow, append_row
from tools.china_quant.regime import classify_regime
from tools.china_quant.report import DailyReport, render_report


FIXTURES = ROOT / "docs" / "test-fixtures" / "china-quant"
LEDGER_BASE = ROOT / "docs" / "ai" / "daily-trading"


def build_report_from_snapshot(snap, *, force_no_trade: bool = False) -> DailyReport:
    fresh = assess_freshness(snap.data_timestamp)
    regime = classify_regime(
        snap.sh_index_change_pct,
        snap.advance_count,
        snap.decline_count,
    )
    if force_no_trade:
        regime.max_primary_candidates = 0

    trade_today = "否（NO TRADE）" if regime.max_primary_candidates == 0 else "谨慎（仅研究/模拟）"
    if not fresh.live_decision_ok:
        trade_today = "否（数据不够新，不适合盘中实盘决策）"

    direction = "偏弱" if (snap.sh_index_change_pct or 0) < -0.5 else "偏强" if (snap.sh_index_change_pct or 0) > 0.5 else "震荡"
    position = "0%" if regime.max_primary_candidates == 0 else "10%-20% 单票上限（模拟）"

    return DailyReport(
        conclusion_direction=direction,
        market_regime_zh=regime.regime.value,
        position_guidance=position,
        trade_today=trade_today,
        data_cutoff=snap.data_timestamp.isoformat(sep=" ", timespec="minutes"),
        data_status=fresh.status.value,
        one_liner=regime.guidance_zh,
        regime=regime,
        freshness=fresh,
        primary=[],
        watchlist=[],
        avoid=["ST板块（默认回避）", "流动性极低个股", "涨停封板难以买入的标的"],
    )


def cmd_premarket(args: argparse.Namespace) -> int:
    if args.fixture:
        snap = snapshot_from_fixture(load_fixture(args.fixture, FIXTURES))
    else:
        try:
            snap = fetch_live_snapshot()
        except Exception as e:
            print(f"BLOCKED_BY_DATA: {e}", file=sys.stderr)
            snap = snapshot_from_fixture(load_fixture("weak_market", FIXTURES))
            snap.source = f"fallback:weak_market ({e})"

    report = build_report_from_snapshot(snap, force_no_trade=args.fixture == "weak_market")
    md = render_report(report)
    out_dir = LEDGER_BASE
    out_dir.mkdir(parents=True, exist_ok=True)
    day = snap.trade_date
    out_path = out_dir / f"{day}_PREMARKET.md"
    out_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n---\nSaved: {out_path}")
    return 0


def cmd_test_freshness(args: argparse.Namespace) -> int:
    stale = snapshot_from_fixture(load_fixture("stale_data", FIXTURES))
    fresh = assess_freshness(stale.data_timestamp, now=datetime.now())
    ok = not fresh.live_decision_ok
    print("PASS" if ok else "FAIL", fresh.message)
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="China A-share outlook (paper only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pm = sub.add_parser("premarket", help="Generate pre-market report")
    pm.add_argument("--fixture", help="Use fixture name instead of live data")
    pm.set_defaults(func=cmd_premarket)
    tf = sub.add_parser("test-freshness", help="Test A — stale data rejection")
    tf.set_defaults(func=cmd_test_freshness)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
