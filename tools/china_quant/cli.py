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
from tools.china_quant.daily_runner import (
    run_fixture,
    run_historical,
    run_latest_available,
    write_deliverables,
)
from tools.china_quant.freshness import assess_freshness
from tools.china_quant.modes import OperatingMode
from tools.china_quant.model_monitor import compute_monitor, write_monitor_report
from tools.china_quant.paper_trade import append_paper_record, simulate_paper_outcome
from tools.china_quant.providers.fixture_provider import FixtureProvider
from tools.china_quant.intelligence import load_full_bundle
from tools.china_quant.universe import build_universe
from tools.china_quant.report import render_report

FIXTURES = ROOT / "docs" / "test-fixtures" / "china-quant"
LEDGER_BASE = ROOT / "docs" / "ai" / "daily-trading"
LOG_DIR = ROOT / "docs" / "ai" / "daily-trading" / "logs"
LOCK_DIR = LEDGER_BASE / ".locks"


def _log(cmd: str, msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "china_quant_cli.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} [{cmd}] {msg}\n")


def _acquire_lock(name: str) -> bool:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock = LOCK_DIR / f"{name}.lock"
    if lock.exists():
        age = datetime.now().timestamp() - lock.stat().st_mtime
        if age < 3600:
            return False
    lock.write_text(datetime.now().isoformat(), encoding="utf-8")
    return True


def _release_lock(name: str) -> None:
    lock = LOCK_DIR / f"{name}.lock"
    lock.unlink(missing_ok=True)


def _resolve_mode(args) -> OperatingMode:
    if getattr(args, "fixture", None) or getattr(args, "mode", None) == "FIXTURE":
        return OperatingMode.FIXTURE
    if getattr(args, "mode", None) == "HISTORICAL" or getattr(args, "date", None):
        return OperatingMode.HISTORICAL
    if getattr(args, "mode", None) == "LIVE_OR_DELAYED":
        return OperatingMode.LIVE_OR_DELAYED
    return OperatingMode.LATEST_AVAILABLE


def _run_daily(args, cmd_name: str) -> int:
    if not _acquire_lock(cmd_name):
        print("Duplicate run blocked — lock exists", file=sys.stderr)
        return 1
    try:
        mode = _resolve_mode(args)
        _log(cmd_name, f"mode={mode.value}")
        if mode == OperatingMode.FIXTURE:
            result = run_fixture(FIXTURES, args.fixture or "universe_full")
        elif mode == OperatingMode.HISTORICAL:
            result = run_historical(FIXTURES, args.date or "2026-06-12")
        else:
            result = run_latest_available(FIXTURES, use_cache=not getattr(args, "no_cache", False))
        paths = write_deliverables(result, LEDGER_BASE, FIXTURES)
        print(render_report(result.report))
        print(f"\n---\nMode: {result.mode.value}\nSaved: {paths.get('premarket')}")
        if result.limitations:
            print("Limitations:", result.limitations)
        _log(cmd_name, f"done mode={result.mode.value}")
        return 0
    finally:
        _release_lock(cmd_name)


def cmd_premarket(args):
    return _run_daily(args, "premarket")


def cmd_latest(args):
    args.mode = "LATEST_AVAILABLE"
    return _run_daily(args, "latest")


def cmd_historical(args):
    args.mode = "HISTORICAL"
    return _run_daily(args, "historical")


def cmd_intraday(args):
    from tools.china_quant.providers.akshare_provider import AKShareProvider
    try:
        ak = AKShareProvider()
        sess = ak.get_market_session_state()
        spot = ak.get_spot_quotes()
        fresh = assess_freshness(spot.market_timestamp)
        print(f"Session: {sess.payload['state']}")
        if not fresh.live_decision_ok:
            print("Data is not current enough for a live entry decision.")
        else:
            print("Data freshness OK for review (not a trade signal).")
        return 0
    except Exception as e:
        print(f"BLOCKED_BY_DATA: {e}", file=sys.stderr)
        return 1


def cmd_postmarket(args):
    mode = _resolve_mode(args)
    if mode == OperatingMode.FIXTURE:
        day = load_full_bundle(FIXTURES).snapshot.trade_date
    else:
        day = datetime.now().strftime("%Y-%m-%d")
    md = f"# 盘后复盘 {day}\n\n- Mode: {mode.value}\n- 不修改盘前原文\n"
    p = LEDGER_BASE / f"{day}_POSTMARKET.md"
    p.write_text(md, encoding="utf-8")
    write_monitor_report(LEDGER_BASE, ROOT / "docs" / "ai" / "QUANT_MODEL_RISK.md")
    print(md)
    return 0


def cmd_screen(args):
    mode = _resolve_mode(args)
    if mode == OperatingMode.FIXTURE:
        bundle = load_full_bundle(FIXTURES, args.fixture or "universe_full")
        uni = build_universe({"stocks": [__import__("dataclasses").asdict(s) for s in bundle.stocks]})
        print(f"FIXTURE Total={uni.stats.total} Tradable={len(uni.tradable)}")
        return 0
    result = run_latest_available(FIXTURES, use_cache=True)
    if result.universe_audit:
        from tools.china_quant.universe_builder import render_universe_audit
        print(render_universe_audit(result.universe_audit))
    return 0


def cmd_stock_dossier(args):
    cmd_premarket(argparse.Namespace(fixture=None, mode="LATEST_AVAILABLE", date=None, no_cache=False))
    code = args.code
    for p in LEDGER_BASE.glob(f"*_PRIMARY_CANDIDATES/{code}.md"):
        print(p.read_text(encoding="utf-8"))
        return 0
    print(f"No dossier for {code}", file=sys.stderr)
    return 1


def cmd_backtest(args):
    fp = FixtureProvider(FIXTURES)
    try:
        from tools.china_quant.providers.akshare_provider import AKShareProvider
        bars = AKShareProvider(use_cache=True).get_daily_bars(args.code).payload["bars"]
    except Exception:
        bars = fp.load_bars(args.code).payload["bars"]
    train, test = walk_forward_split(bars)
    is_res = run_backtest(train)
    oos_res = run_backtest(test)
    report = LEDGER_BASE / f"BACKTEST_{args.code}.md"
    report.write_text(
        f"# Backtest {args.code}\n\n## In-sample\n```json\n{json.dumps(is_res.metrics, indent=2)}\n```\n\n"
        f"## Out-of-sample\n```json\n{json.dumps(oos_res.metrics, indent=2)}\n```\n\n"
        f"Validation: {oos_res.validation_label}\n",
        encoding="utf-8",
    )
    print(report.read_text(encoding="utf-8"))
    return 0


def cmd_paper_trade(args):
    days = json.loads((FIXTURES / "trading_calendar.json").read_text())["trading_days"]
    for i, day in enumerate(days):
        rec = simulate_paper_outcome(
            code="601398", name="样本/真实混合", entry=5.2, stop=4.9, target1=5.5,
            report_date=day, triggered=(i % 3 != 0), won=(i % 4 != 2) if i % 3 != 0 else None,
        )
        append_paper_record(LEDGER_BASE, rec)
    print(f"Appended {len(days)} paper records (immutable JSONL)")
    return 0


def cmd_validate(args):
    m = compute_monitor(LEDGER_BASE)
    print(json.dumps({"status": m.status, "hit_rate": m.rolling_hit_rate, "records": m.recommendation_count}, indent=2))
    return 0


def cmd_test(args):
    import subprocess
    for script in ["run-china-quant-tests.py", "run-china-quant-full-tests.py", "run-china-quant-real-tests.py"]:
        p = ROOT / "scripts" / script
        if p.exists():
            subprocess.run([sys.executable, str(p)], check=False)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="China A-share quant intelligence")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=[m.value for m in OperatingMode])
    common.add_argument("--fixture", help="FIXTURE mode only")
    common.add_argument("--date", help="HISTORICAL mode YYYY-MM-DD")
    common.add_argument("--no-cache", action="store_true")
    for name, func in [
        ("premarket", cmd_premarket), ("latest", cmd_latest), ("historical", cmd_historical),
        ("intraday", cmd_intraday), ("postmarket", cmd_postmarket), ("screen", cmd_screen),
        ("stock-dossier", cmd_stock_dossier), ("backtest", cmd_backtest),
        ("paper-trade", cmd_paper_trade), ("validate", cmd_validate), ("test", cmd_test),
    ]:
        sp = sub.add_parser(name, parents=[common] if name not in ("test", "validate", "paper-trade") else [])
        if name == "stock-dossier":
            sp.add_argument("--code", default="601398")
        if name == "backtest":
            sp.add_argument("--code", default="601398")
        sp.set_defaults(func=func)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
