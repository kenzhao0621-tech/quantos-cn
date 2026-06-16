#!/usr/bin/env python3
"""V4 quant CLI — JSON output + 中文摘要."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED, __version__
from quant._config import _DEFAULT_COVERAGE, load_config
from quant.acceptance import run_real_data_acceptance
from quant.capability_report import generate_capability_report
from quant.composite_provider import CompositeMarketDataProvider
from quant.data_lake import load_latest_normalized, save_snapshot
from quant.data_quality import run_snapshot_quality_checks
from quant.provider_health import run_provider_checks
from quant.providers.manual_snapshot import ManualSnapshotProvider


def _emit(payload: dict[str, Any], summary_zh: str, *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"\n【摘要】{summary_zh}", file=sys.stderr)
    return exit_code


def cmd_system_audit(_args: argparse.Namespace) -> int:
    payload = {
        "version": __version__,
        "paper_trading_only": PAPER_TRADING_ONLY,
        "real_money_execution_disabled": REAL_MONEY_EXECUTION_DISABLED,
        "root": str(ROOT),
        "config_dir": str(ROOT / "config"),
        "data_dir": str(ROOT / "data"),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    ok = PAPER_TRADING_ONLY and REAL_MONEY_EXECUTION_DISABLED
    return _emit(
        payload,
        "系统审计完成：仅纸面交易，真实下单已禁用。" if ok else "安全门未满足，请检查 quant 包常量。",
        exit_code=0 if ok else 2,
    )


def cmd_data_coverage(_args: argparse.Namespace) -> int:
    coverage = load_config("data_coverage", defaults=_DEFAULT_COVERAGE)
    domains = coverage.get("domains", {})
    available = sum(1 for d in domains.values() if d.get("status") == "available")
    partial = sum(1 for d in domains.values() if d.get("status") == "partial")
    return _emit(
        coverage,
        f"数据覆盖矩阵：{len(domains)} 个域，可用 {available}，部分 {partial}。",
    )


def cmd_provider_check(args: argparse.Namespace) -> int:
    result = run_provider_checks(probe_live=args.live)
    failed = [r for r in result["providers"] if not r.get("configured")]
    return _emit(
        result,
        f"提供商检查完成（live={args.live}），未配置 {len(failed)} 个。",
        exit_code=0,
    )


def cmd_fetch_market_snapshot(args: argparse.Namespace) -> int:
    composite = CompositeMarketDataProvider()
    datasets = args.datasets.split(",") if args.datasets else None
    results = composite.fetch_market_snapshot(datasets=datasets)
    ok_count = sum(1 for r in results.values() if r.ok)
    payload = {k: v.to_dict() for k, v in results.items()}
    if args.persist:
        for ds, cr in results.items():
            if cr.ok and cr.result:
                save_snapshot(
                    ds,
                    raw_payload=cr.result.payload,
                    normalized_payload=cr.result.payload,
                    provider=cr.result.provider,
                )
    return _emit(
        {"datasets": payload, "success_count": ok_count, "total": len(results)},
        f"市场快照抓取：{ok_count}/{len(results)} 个数据集成功。",
        exit_code=0 if ok_count else 1,
    )


def cmd_validate_latest_snapshot(args: argparse.Namespace) -> int:
    dataset = args.dataset or "spot_quotes"
    doc = load_latest_normalized(dataset, trade_date=args.date)
    if not doc:
        return _emit(
            {"dataset": dataset, "found": False},
            f"未找到 {dataset} 的最新快照。",
            exit_code=1,
        )
    payload = doc.get("payload")
    qr = run_snapshot_quality_checks(dataset, payload, data_hash=doc.get("data_hash", ""))
    return _emit(
        {"dataset": dataset, "found": True, "quality": qr.to_dict()},
        "快照质量校验通过。" if qr.passed else f"快照质量校验失败：{'; '.join(qr.errors)}",
        exit_code=0 if qr.passed else 1,
    )


def cmd_import_snapshot(args: argparse.Namespace) -> int:
    path = Path(args.path)
    dataset = args.dataset or "spot_quotes"
    provider = ManualSnapshotProvider()
    result = provider.load_file(path, dataset=dataset)
    if result.ok and args.persist:
        save_snapshot(
            dataset,
            raw_payload=result.payload,
            normalized_payload=result.payload,
            provider=provider.name,
        )
    return _emit(
        result.to_dict(),
        f"手动导入{'成功' if result.ok else '失败'}：{path.name}",
        exit_code=0 if result.ok else 1,
    )


def cmd_run_daily(args: argparse.Namespace) -> int:
    from tools.china_quant.daily_runner import run_fixture, run_latest_available, write_deliverables

    fixtures = ROOT / "docs" / "test-fixtures" / "china-quant"
    ledger = ROOT / "docs" / "ai" / "daily-trading"
    try:
        if args.fixture:
            result = run_fixture(fixtures, args.fixture)
            mode = "FIXTURE"
        else:
            result = run_latest_available(fixtures, use_cache=not args.no_cache)
            mode = result.mode.value
        paths = write_deliverables(result, ledger, fixtures)
        return _emit(
            {
                "mode": mode,
                "analysis_date": result.analysis_date,
                "paths": {k: str(v) for k, v in paths.items()},
                "limitations": result.limitations,
            },
            f"每日流程完成（{mode}），输出已写入 deliverables。",
        )
    except Exception as e:
        return _emit({"error": str(e)}, f"每日流程失败：{e}", exit_code=1)


def cmd_health_check(args: argparse.Namespace) -> int:
    health = run_provider_checks(probe_live=args.live)
    acceptance = run_real_data_acceptance(persist=False)
    ok = acceptance.get("accepted", False) or not args.strict
    payload = {"health": health, "acceptance": acceptance}
    return _emit(
        payload,
        "健康检查通过。" if ok else "健康检查未完全通过（数据或提供商异常）。",
        exit_code=0 if ok else 1,
    )


def cmd_scheduler_dry_run(_args: argparse.Namespace) -> int:
    schedule = [
        {"time": "08:30", "command": "fetch-market-snapshot", "persist": True},
        {"time": "08:35", "command": "validate-latest-snapshot", "dataset": "spot_quotes"},
        {"time": "08:40", "command": "run-daily"},
        {"time": "15:30", "command": "evaluate-paper-trades"},
    ]
    return _emit(
        {"dry_run": True, "schedule": schedule, "paper_trading_only": True},
        f"调度干跑：{len(schedule)} 个任务已列出（未执行）。",
    )


def cmd_build_validation_summary(_args: argparse.Namespace) -> int:
    report = generate_capability_report(probe_live=False, run_acceptance=True)
    return _emit(
        report,
        f"能力报告已生成：{report.get('paths', {})}",
    )


def cmd_evaluate_paper_trades(_args: argparse.Namespace) -> int:
    from tools.china_quant.model_monitor import compute_monitor

    ledger = ROOT / "docs" / "ai" / "daily-trading"
    monitor = compute_monitor(ledger)
    payload = {
        "status": monitor.status,
        "hit_rate": monitor.rolling_hit_rate,
        "recommendation_count": monitor.recommendation_count,
        "paper_trading_only": True,
    }
    return _emit(
        payload,
        f"纸面交易评估：状态 {monitor.status}，命中率 {monitor.rolling_hit_rate:.1%}。",
        exit_code=0,
    )


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "system-audit": cmd_system_audit,
    "data-coverage": cmd_data_coverage,
    "provider-check": cmd_provider_check,
    "fetch-market-snapshot": cmd_fetch_market_snapshot,
    "validate-latest-snapshot": cmd_validate_latest_snapshot,
    "import-snapshot": cmd_import_snapshot,
    "run-daily": cmd_run_daily,
    "health-check": cmd_health_check,
    "scheduler-dry-run": cmd_scheduler_dry_run,
    "build-validation-summary": cmd_build_validation_summary,
    "evaluate-paper-trades": cmd_evaluate_paper_trades,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4 China A-share quant CLI (paper only)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("system-audit", help="Audit safety gates and paths")
    sub.add_parser("data-coverage", help="Show data coverage matrix")

    p_check = sub.add_parser("provider-check", help="Provider capability table")
    p_check.add_argument("--live", action="store_true", help="Probe providers live")

    p_fetch = sub.add_parser("fetch-market-snapshot", help="Fetch routed market data")
    p_fetch.add_argument("--datasets", help="Comma-separated dataset names")
    p_fetch.add_argument("--persist", action="store_true", help="Save to data lake")

    p_val = sub.add_parser("validate-latest-snapshot", help="Validate normalized snapshot")
    p_val.add_argument("--dataset", default="spot_quotes")
    p_val.add_argument("--date", help="YYYY-MM-DD")

    p_imp = sub.add_parser("import-snapshot", help="Import CSV/JSON manual snapshot")
    p_imp.add_argument("path", help="Path to CSV or JSON file")
    p_imp.add_argument("--dataset", default="spot_quotes")
    p_imp.add_argument("--persist", action="store_true")

    p_daily = sub.add_parser("run-daily", help="Run daily intelligence pipeline")
    p_daily.add_argument("--fixture", help="Fixture name for offline run")
    p_daily.add_argument("--no-cache", action="store_true")

    p_health = sub.add_parser("health-check", help="Health + acceptance check")
    p_health.add_argument("--live", action="store_true")
    p_health.add_argument("--strict", action="store_true", help="Fail if acceptance fails")

    sub.add_parser("scheduler-dry-run", help="Print scheduled jobs without running")
    sub.add_parser("build-validation-summary", help="Generate capability report")
    sub.add_parser("evaluate-paper-trades", help="Evaluate paper trade ledger")

    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
