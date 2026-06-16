#!/usr/bin/env python3
"""CLI for China A-share daily outlook (paper trading only)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.china_quant.calendar import is_trading_day
from tools.china_quant.data import fetch_live_snapshot, load_fixture, snapshot_from_fixture
from tools.china_quant.freshness import assess_freshness
from tools.china_quant.ledger import LedgerRow, append_row
from tools.china_quant.models import bundle_from_fixture
from tools.china_quant.pipeline import load_bundle, run_pipeline
from tools.china_quant.report import render_report


FIXTURES = ROOT / "docs" / "test-fixtures" / "china-quant"
LEDGER_BASE = ROOT / "docs" / "ai" / "daily-trading"


def _fixture_reference_now(fixture_name: str, bundle) -> datetime:
    """Premarket context: morning after fixture close (not wall-clock)."""
    if fixture_name == "stale_data":
        return datetime.now()
    return bundle.snapshot.data_timestamp + timedelta(hours=16)


def cmd_premarket(args: argparse.Namespace) -> int:
    if args.fixture:
        bundle = load_bundle(args.fixture, FIXTURES)
        ref_now = _fixture_reference_now(args.fixture, bundle)
        result = run_pipeline(bundle, fixtures_dir=FIXTURES, now=ref_now)
        md = render_report(result.report)
        day = bundle.snapshot.trade_date
    else:
        if not is_trading_day(datetime.now().strftime("%Y-%m-%d"), fixtures_dir=FIXTURES):
            print("NOTE: calendar heuristic — may be non-trading day", file=sys.stderr)
        try:
            snap = fetch_live_snapshot()
            bundle = bundle_from_fixture({
                "trade_date": snap.trade_date,
                "sh_index_close": snap.sh_index_close,
                "sh_index_change_pct": snap.sh_index_change_pct,
                "sz_index_close": snap.sz_index_close,
                "cyb_index_change_pct": snap.cyb_index_change_pct,
                "data_timestamp": snap.data_timestamp.isoformat(),
                "source": snap.source,
                "status": snap.status,
                "advance_count": snap.advance_count,
                "decline_count": snap.decline_count,
                "sectors": [],
                "stocks": [],
                "fixture_label": "LIVE_AKSHARE — 指数延迟数据；个股未拉取",
            })
            result = run_pipeline(bundle, fixtures_dir=FIXTURES)
            md = render_report(result.report)
            day = snap.trade_date
        except Exception as e:
            print(f"BLOCKED_BY_DATA: {e}", file=sys.stderr)
            return 1

    out_dir = LEDGER_BASE
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{day}_PREMARKET.md"
    out_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n---\nSaved: {out_path}")
    return 0


def cmd_postmarket(args: argparse.Namespace) -> int:
    fixture = args.fixture or "bullish_market"
    bundle = load_bundle(fixture, FIXTURES)
    ref_now = _fixture_reference_now(fixture, bundle)
    result = run_pipeline(bundle, fixtures_dir=FIXTURES, now=ref_now)
    day = bundle.snapshot.trade_date
    lines = [
        f"# A股盘后复盘 — {day}",
        "",
        "## 样本说明",
        f"- {bundle.fixture_label or 'fixture'}",
        "- 本复盘为样本/fixture，不修改盘前原文",
        "",
        "## 当日结论回顾",
        result.report.one_liner,
        "",
        "## 首选标的跟踪",
    ]
    if result.report.primary:
        for c in result.report.primary:
            lines.append(f"- {c.name}({c.code})：模拟持有观察，止损 {c.stop}")
    else:
        lines.append("- 无首选（NO TRADE 或观望）")
    lines += ["", "## 经验教训", "- 遵守止损；弱势日正确观望是成功", ""]
    md = "\n".join(lines)
    out_path = LEDGER_BASE / f"{day}_POSTMARKET.md"
    out_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n---\nSaved: {out_path}")
    return 0


def cmd_test_freshness(args: argparse.Namespace) -> int:
    bundle = load_bundle("stale_data", FIXTURES)
    fresh = assess_freshness(bundle.snapshot.data_timestamp, now=datetime.now())
    ok = not fresh.live_decision_ok
    print("PASS" if ok else "FAIL", fresh.message)
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="China A-share outlook (paper only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pm = sub.add_parser("premarket", help="Generate pre-market report")
    pm.add_argument("--fixture", help="Use fixture name instead of live data")
    pm.set_defaults(func=cmd_premarket)
    po = sub.add_parser("postmarket", help="Generate post-market review (fixture)")
    po.add_argument("--fixture", help="Fixture name", default="bullish_market")
    po.set_defaults(func=cmd_postmarket)
    tf = sub.add_parser("test-freshness", help="Test A — stale data rejection")
    tf.set_defaults(func=cmd_test_freshness)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
