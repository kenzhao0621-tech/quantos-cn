#!/usr/bin/env python3
"""CLI for China A-share quant intelligence (paper trading only)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.china_quant.backtest.engine import run_backtest, walk_forward_split
from tools.china_quant.data import load_fixture
from tools.china_quant.freshness import assess_freshness
from tools.china_quant.intelligence import load_full_bundle, run_intelligence
from tools.china_quant.model_monitor import compute_monitor, write_monitor_report
from tools.china_quant.paper_trade import append_paper_record, simulate_paper_outcome
from tools.china_quant.pipeline import load_bundle, run_pipeline
from tools.china_quant.providers.fixture_provider import FixtureProvider
from tools.china_quant.report import render_report
from tools.china_quant.universe import build_universe

FIXTURES = ROOT / "docs" / "test-fixtures" / "china-quant"
LEDGER_BASE = ROOT / "docs" / "ai" / "daily-trading"
LOG_DIR = ROOT / "docs" / "ai" / "logs"


def _log(cmd: str, msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} [{cmd}] {msg}\n"
    with (LOG_DIR / "china_quant_cli.log").open("a", encoding="utf-8") as f:
        f.write(line)


def _fixture_ref_now(name: str, bundle) -> datetime:
    if name == "stale_data":
        return datetime.now()
    return bundle.snapshot.data_timestamp + timedelta(hours=16)


def _write_premarket(result, day: str) -> Path:
    out = LEDGER_BASE / f"{day}_PREMARKET.md"
    out.write_text(render_report(result.report), encoding="utf-8")
    cand_dir = LEDGER_BASE / f"{day}_PRIMARY_CANDIDATES"
    cand_dir.mkdir(parents=True, exist_ok=True)
    for code, md in result.dossiers.items():
        (cand_dir / f"{code}.md").write_text(md, encoding="utf-8")
    if result.report.watchlist:
        wl = LEDGER_BASE / f"{day}_WATCHLIST.md"
        lines = ["# 观察名单\n"]
        for c in result.report.watchlist:
            lines.append(f"- **{c.name} ({c.code})** 评分{c.score:.0f}")
        wl.write_text("\n".join(lines), encoding="utf-8")
    return out


def cmd_premarket(args: argparse.Namespace) -> int:
    _log("premarket", f"start fixture={args.fixture}")
    fp = FixtureProvider(FIXTURES)
    policy = fp.load_policy().payload
    inst = fp.load_institutional().payload
    bundle = load_full_bundle(FIXTURES, args.fixture or "universe_full")
    result = run_intelligence(bundle, fixtures_dir=FIXTURES, policy_data=policy, inst_data=inst,
                              now=_fixture_ref_now(args.fixture or "universe_full", bundle))
    path = _write_premarket(result, bundle.snapshot.trade_date)
    print(render_report(result.report))
    print(f"\n---\nSaved: {path}\nUniverse: {result.universe_stats}")
    _log("premarket", f"done {path}")
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    bundle = load_full_bundle(FIXTURES, args.fixture or "universe_full")
    uni = build_universe({"stocks": [__import__("dataclasses").asdict(s) for s in bundle.stocks]})
    print(f"Total={uni.stats.total} Tradable={len(uni.tradable)} Excluded={len(uni.excluded)}")
    for st, r in uni.excluded[:10]:
        print(f"  EXCL {st.code} {r}")
    return 0


def cmd_stock_dossier(args: argparse.Namespace) -> int:
    cmd_premarket(argparse.Namespace(fixture=args.fixture or "universe_full"))
    code = args.code
    p = LEDGER_BASE / f"{load_full_bundle(FIXTURES).snapshot.trade_date}_PRIMARY_CANDIDATES" / f"{code}.md"
    if p.exists():
        print(p.read_text(encoding="utf-8"))
        return 0
    print(f"No dossier for {code}", file=sys.stderr)
    return 1


def cmd_backtest(args: argparse.Namespace) -> int:
    fp = FixtureProvider(FIXTURES)
    bars_env = fp.load_bars(args.code or "601398")
    bars = bars_env.payload["bars"]
    train, test = walk_forward_split(bars)
    is_res = run_backtest(train)
    oos_res = run_backtest(test)
    print("In-sample:", json.dumps(is_res.metrics, indent=2))
    print("Out-of-sample:", json.dumps(oos_res.metrics, indent=2))
    print("Validation:", oos_res.validation_label)
    return 0


def cmd_paper_trade(args: argparse.Namespace) -> int:
    days = json.loads((FIXTURES / "trading_calendar.json").read_text())["trading_days"][:10]
    for i, day in enumerate(days):
        won = i % 3 != 2
        rec = simulate_paper_outcome(
            code="601398", name="样本工行", entry=5.2, stop=4.9, target1=5.5,
            report_date=day, triggered=(i % 4 != 0), won=won if i % 4 != 0 else None,
        )
        append_paper_record(LEDGER_BASE, rec)
    print(f"Appended {len(days)} paper records")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    m = compute_monitor(LEDGER_BASE)
    print(json.dumps({"status": m.status, "hit_rate": m.rolling_hit_rate, "records": m.recommendation_count}, indent=2))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run-china-quant-full-tests.py")])
    return r.returncode


def cmd_historical(args: argparse.Namespace) -> int:
    return cmd_premarket(argparse.Namespace(fixture="universe_full"))


def cmd_latest(args: argparse.Namespace) -> int:
    print("BLOCKED_BY_DATA: use --fixture for deterministic mode; live requires trading session", file=sys.stderr)
    return cmd_premarket(argparse.Namespace(fixture=args.fixture or "universe_full"))


def cmd_intraday(args: argparse.Namespace) -> int:
    bundle = load_bundle("stale_data", FIXTURES)
    fresh = assess_freshness(bundle.snapshot.data_timestamp, now=datetime.now())
    print("Data is not current enough for a live entry decision." if not fresh.live_decision_ok else "DELAYED OK for review only")
    return 0 if not fresh.live_decision_ok else 0


def cmd_postmarket(args: argparse.Namespace) -> int:
    bundle = load_full_bundle(FIXTURES, args.fixture or "universe_full")
    day = bundle.snapshot.trade_date
    md = f"# 盘后复盘 {day}\n\n- 样本/fixture复盘\n- 不修改盘前原文\n- 遵守止损纪律\n"
    p = LEDGER_BASE / f"{day}_POSTMARKET.md"
    p.write_text(md, encoding="utf-8")
    write_monitor_report(LEDGER_BASE, ROOT / "docs" / "ai" / "QUANT_MODEL_RISK.md")
    print(md)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="China A-share quant intelligence")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, func, help_ in [
        ("premarket", cmd_premarket, "Pre-market full-universe report"),
        ("intraday", cmd_intraday, "Intraday freshness check"),
        ("postmarket", cmd_postmarket, "Post-market review"),
        ("historical", cmd_historical, "Historical fixture report"),
        ("latest", cmd_latest, "Latest-available (fixture fallback)"),
        ("screen", cmd_screen, "Universe screen stats"),
        ("stock-dossier", cmd_stock_dossier, "Single stock dossier"),
        ("backtest", cmd_backtest, "Run backtest on bar fixture"),
        ("paper-trade", cmd_paper_trade, "Append paper trade records"),
        ("validate", cmd_validate, "Model validation status"),
        ("test", cmd_test, "Run full test suite"),
    ]:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--fixture", help="Fixture name")
        if name == "stock-dossier":
            sp.add_argument("--code", default="601398")
        if name == "backtest":
            sp.add_argument("--code", default="601398")
        sp.set_defaults(func=func)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
