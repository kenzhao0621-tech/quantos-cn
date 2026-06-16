#!/usr/bin/env python3
"""V4 quant CLI — JSON output + 中文摘要."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
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
from quant.data_lake import DATA_ROOT, load_by_run_id, load_latest_normalized, save_snapshot
from quant.data_quality import run_snapshot_quality_checks
from quant.provider_health import run_provider_checks
from quant.providers.manual_snapshot import ManualSnapshotProvider
from quant.run_context import new_run_id, set_run_id
from quant.secret_loader import configured as secret_configured


def _emit(payload: dict[str, Any], summary_zh: str, *, exit_code: int = 0) -> int:
    payload["exit_code"] = exit_code
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
        "data_dir": str(DATA_ROOT),
        "tushare_token_configured": secret_configured("TUSHARE_TOKEN"),
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
    result = run_provider_checks(
        probe_live=args.live,
        provider_filter=getattr(args, "provider", None),
    )
    failed = [r for r in result["providers"] if not r.get("configured")]
    return _emit(
        result,
        f"提供商检查完成（live={args.live}），未配置 {len(failed)} 个。",
        exit_code=0,
    )


def cmd_fetch_market_snapshot(args: argparse.Namespace) -> int:
    run_id = new_run_id()
    set_run_id(run_id)
    composite = CompositeMarketDataProvider()
    if getattr(args, "live_only", False) and "manual_snapshot" in composite.registry:
        del composite.registry["manual_snapshot"]

    fetch_kwargs: dict[str, Any] = {
        "live_only": getattr(args, "live_only", False),
        "route_mode": "latest_available" if getattr(args, "latest_available", False) else None,
        "provider_filter": getattr(args, "provider", None),
    }
    datasets = args.datasets.split(",") if args.datasets else None
    results = composite.fetch_market_snapshot(datasets=datasets, **fetch_kwargs)
    ok_count = sum(1 for r in results.values() if r.ok)
    manifests: list[dict[str, Any]] = []

    if args.persist:
        for ds, cr in results.items():
            if cr.ok and cr.result:
                manifest = save_snapshot(
                    ds,
                    run_id=run_id,
                    raw_payload=cr.result.payload,
                    normalized_payload=cr.result.payload,
                    provider=cr.result.provider,
                    provenance={
                        "endpoint": cr.result.endpoint,
                        "source_dataset": cr.result.source_dataset,
                        "freshness": cr.result.freshness,
                        "is_live": cr.result.is_live,
                        "is_end_of_day": cr.result.is_end_of_day,
                        "is_manual": cr.result.is_manual,
                        "is_fixture": cr.result.is_fixture,
                        "market_date": cr.result.market_date,
                    },
                )
                manifests.append(manifest.to_dict())

    spot = results.get("spot_quotes")
    winner = spot.result if spot and spot.result else None
    payload = {
        "run_id": run_id,
        "datasets": {k: v.to_dict() for k, v in results.items()},
        "success_count": ok_count,
        "total": len(results),
        "selected_provider": winner.provider if winner else None,
        "selection_reason": spot.selection_reason if spot else "",
        "market_date": winner.market_date if winner else "",
        "freshness": winner.freshness if winner else "",
        "row_count": winner.row_count if winner else 0,
        "manifests": manifests,
        "manifest_path": str(DATA_ROOT / "manifests" / run_id) if manifests else "",
        "recovery_action": "validate with --run-id" if ok_count else "check provider attempts",
    }
    return _emit(
        payload,
        f"市场快照抓取 run_id={run_id}：{ok_count}/{len(results)} 个数据集成功。",
        exit_code=0 if ok_count else 1,
    )


def cmd_validate_latest_snapshot(args: argparse.Namespace) -> int:
    dataset = args.dataset or "spot_quotes"
    requested_run_id = getattr(args, "run_id", None)

    if requested_run_id:
        doc = load_by_run_id(dataset, requested_run_id)
    else:
        doc = load_latest_normalized(dataset, trade_date=args.date)

    base = {
        "dataset": dataset,
        "requested_run_id": requested_run_id,
        "found": bool(doc),
    }

    if not doc:
        return _emit(
            {**base, "recovery_action": "fetch with --persist first"},
            f"未找到 {dataset} 的快照（run_id={requested_run_id or 'latest'}）。",
            exit_code=2,
        )

    resolved_run_id = doc.get("run_id", "")
    provider = doc.get("provider", "")
    source_dataset = doc.get("source_dataset", doc.get("payload", {}).get("source_dataset", "") if isinstance(doc.get("payload"), dict) else "")
    market_date = doc.get("market_date", doc.get("payload", {}).get("market_date", "") if isinstance(doc.get("payload"), dict) else "")
    retrieved_at = doc.get("saved_at", "")
    freshness = doc.get("freshness", "")
    is_live = bool(doc.get("is_live"))
    is_eod = bool(doc.get("is_end_of_day"))
    is_manual = bool(doc.get("is_manual")) or provider == "manual_snapshot"
    is_fixture = bool(doc.get("is_fixture"))

    if requested_run_id and resolved_run_id != requested_run_id:
        return _emit(
            {**base, "resolved_run_id": resolved_run_id, "recovery_action": "use correct run_id"},
            f"run_id 不匹配：请求 {requested_run_id}，解析 {resolved_run_id}。",
            exit_code=7,
        )

    if getattr(args, "provider", None) and provider != args.provider:
        return _emit(
            {**base, "resolved_run_id": resolved_run_id, "provider": provider},
            f"提供商不匹配：期望 {args.provider}，实际 {provider}。",
            exit_code=6,
        )

    if getattr(args, "market_date", None) and market_date and market_date != args.market_date:
        return _emit(
            {**base, "market_date": market_date},
            f"市场日期不匹配：期望 {args.market_date}，实际 {market_date}。",
            exit_code=9,
        )

    if getattr(args, "max_age_minutes", None) and retrieved_at:
        try:
            saved = datetime.fromisoformat(retrieved_at)
            age = (datetime.now() - saved).total_seconds() / 60
            if age > args.max_age_minutes:
                return _emit(
                    {**base, "age_minutes": round(age, 1), "retrieved_at": retrieved_at},
                    f"快照过期：{age:.0f} 分钟 > {args.max_age_minutes}。",
                    exit_code=3,
                )
        except ValueError:
            pass

    if getattr(args, "require_live", False):
        if is_manual or is_fixture:
            return _emit(
                {**base, "is_manual": is_manual, "is_fixture": is_fixture},
                "require-live：拒绝 manual/fixture 数据。",
                exit_code=4,
            )
        if not is_live or is_eod:
            return _emit(
                {**base, "is_live": is_live, "is_end_of_day": is_eod, "freshness": freshness},
                "require-live：新鲜度不满足（需 is_live=true）。",
                exit_code=8,
            )

    if getattr(args, "require_non_fixture", False):
        if is_fixture or (is_manual and provider == "manual_snapshot"):
            return _emit(
                {**base, "is_manual": is_manual, "is_fixture": is_fixture},
                "require-non-fixture：拒绝 fixture/manual 数据。",
                exit_code=4,
            )
        if is_eod and not getattr(args, "allow_end_of_day", False):
            return _emit(
                {**base, "is_end_of_day": is_eod, "freshness": freshness},
                "END_OF_DAY 数据需 --allow-end-of-day。",
                exit_code=8,
            )

    payload_data = doc.get("payload")
    qr = run_snapshot_quality_checks(
        dataset,
        payload_data,
        data_hash=doc.get("data_hash", ""),
        provider=provider,
        source_dataset=source_dataset,
        doc_meta={
            "is_fixture": is_fixture,
            "is_manual": is_manual,
            "require_non_fixture": getattr(args, "require_non_fixture", False),
            "freshness": freshness,
        },
    )

    result = {
        **base,
        "resolved_run_id": resolved_run_id,
        "provider": provider,
        "source_dataset": source_dataset,
        "market_date": market_date,
        "retrieved_at": retrieved_at,
        "freshness": freshness,
        "row_count": qr.row_count,
        "is_live": is_live,
        "is_end_of_day": is_eod,
        "is_manual": is_manual,
        "is_fixture": is_fixture,
        "quality": qr.to_dict(),
        "quality_status": "passed" if qr.passed else "failed",
        "normalized_path": doc.get("normalized_path", ""),
        "recovery_action": "none" if qr.passed else "refetch or fix data",
    }

    if not qr.passed:
        return _emit(
            result,
            f"快照质量校验失败：{'; '.join(qr.errors + qr.missing_fields)}",
            exit_code=5,
        )

    return _emit(result, "快照质量校验通过。", exit_code=0)


def cmd_import_snapshot(args: argparse.Namespace) -> int:
    run_id = new_run_id()
    path = Path(args.path)
    dataset = args.dataset or "spot_quotes"
    provider = ManualSnapshotProvider()
    result = provider.load_file(path, dataset=dataset)
    manifest = None
    if result.ok and args.persist:
        manifest = save_snapshot(
            dataset,
            run_id=run_id,
            raw_payload=result.payload,
            normalized_payload=result.payload,
            provider=provider.name,
            provenance={"is_manual": True, "is_live": False},
        )
    payload = {**result.to_dict(), "run_id": run_id}
    if manifest:
        payload["manifest"] = manifest.to_dict()
    return _emit(
        payload,
        f"手动导入{'成功' if result.ok else '失败'}：{path.name}",
        exit_code=0 if result.ok else 1,
    )


def cmd_run_daily(args: argparse.Namespace) -> int:
    from tools.china_quant.daily_runner import run_fixture, run_latest_available, write_deliverables

    from quant.data_lake import load_by_run_id
    from quant.paper_ledger import DuplicateRunError, append_daily_signals

    fixtures = ROOT / "docs" / "test-fixtures" / "china-quant"
    ledger = ROOT / "docs" / "ai" / "daily-trading"
    run_id = getattr(args, "run_id", None)
    mode_name = getattr(args, "mode", None)
    ledger_result: dict[str, Any] | None = None

    try:
        if args.fixture:
            result = run_fixture(fixtures, args.fixture)
            mode = "FIXTURE"
        elif run_id:
            from quant.run_daily_bridge import run_from_run_id

            result = run_from_run_id(run_id, fixtures)
            mode = f"LATEST_AVAILABLE(run_id={run_id})"
        elif mode_name == "latest-available":
            result = run_latest_available(fixtures, use_cache=not args.no_cache)
            mode = result.mode.value
            run_id = (result.provider_status or {}).get("run_id")
        else:
            result = run_latest_available(fixtures, use_cache=not args.no_cache)
            mode = result.mode.value
            run_id = (result.provider_status or {}).get("run_id")
        paths = write_deliverables(result, ledger, fixtures)

        if not args.fixture and run_id:
            spot_doc = load_by_run_id("spot_quotes", run_id) or {}
            try:
                append_out = append_daily_signals(
                    ledger,
                    result,
                    run_id=run_id,
                    provider=spot_doc.get("provider"),
                    freshness=spot_doc.get("freshness"),
                    market_data_date=spot_doc.get("market_date") or result.analysis_date,
                )
                ledger_result = append_out.to_dict()
            except DuplicateRunError as exc:
                ledger_result = {
                    "skipped_duplicate": True,
                    "run_id": run_id,
                    "existing_record_ids": exc.existing_ids,
                }

        return _emit(
            {
                "mode": mode,
                "run_id": run_id,
                "analysis_date": result.analysis_date,
                "provider_status": result.provider_status,
                "paths": {k: str(v) for k, v in paths.items()},
                "limitations": result.limitations,
                "primary_count": len(result.report.primary),
                "paper_ledger": ledger_result,
            },
            f"每日流程完成（{mode}），输出已写入 deliverables。",
        )
    except Exception as e:
        return _emit({"error": str(e), "run_id": run_id}, f"每日流程失败：{e}", exit_code=1)


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


def cmd_fabric_fetch(args: argparse.Namespace) -> int:
    from quant.market_data_fabric import MarketDataFabric

    run_id = new_run_id()
    set_run_id(run_id)
    fabric = MarketDataFabric()
    datasets = args.datasets.split(",") if args.datasets else ["spot_quotes"]
    results = fabric.fetch_market_snapshot(
        datasets=datasets,
        live_only=args.live_only,
        require_live=args.require_live,
    )
    ok_count = sum(1 for r in results.values() if r.ok)
    if args.persist:
        for ds, fr in results.items():
            if fr.ok and fr.result:
                save_snapshot(
                    ds, run_id=run_id,
                    raw_payload=fr.result.payload,
                    normalized_payload=fr.result.payload,
                    provider=fr.result.provider,
                    provenance={"freshness": fr.result.freshness, "is_live": fr.result.is_live},
                )
    payload = {
        "run_id": run_id,
        "datasets": {k: v.to_dict() for k, v in results.items()},
        "ok_count": ok_count,
    }
    blocked = args.require_live and ok_count == 0
    return _emit(
        payload,
        f"Fabric 拉取完成：{ok_count}/{len(results)} 成功。",
        exit_code=2 if blocked else 0,
    )


def cmd_capability_discovery(args: argparse.Namespace) -> int:
    from quant.market_data_fabric import MarketDataFabric
    from quant.provider_base_v2 import discover_capabilities

    fabric = MarketDataFabric()
    report = discover_capabilities(fabric.registry, probe_live=args.live)
    return _emit(report.to_dict(), f"能力发现：{len(report.providers)} 个提供商。")


def cmd_freshness_watchdog(_args: argparse.Namespace) -> int:
    from quant.freshness_watchdog import run_freshness_watchdog
    from quant.market_data_fabric import MarketDataFabric

    report = run_freshness_watchdog(fabric=MarketDataFabric(), probe_live=True)
    blocked = any(v.get("blocked") for v in report.get("datasets", {}).values() if isinstance(v, dict))
    return _emit(report, "新鲜度看门狗完成。", exit_code=2 if blocked else 0)


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
    "fabric-fetch": cmd_fabric_fetch,
    "capability-discovery": cmd_capability_discovery,
    "freshness-watchdog": cmd_freshness_watchdog,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4 China A-share quant CLI (paper only)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("system-audit", help="Audit safety gates and paths")
    sub.add_parser("data-coverage", help="Show data coverage matrix")

    p_check = sub.add_parser("provider-check", help="Provider capability table")
    p_check.add_argument("--live", action="store_true", help="Probe providers live")
    p_check.add_argument("--provider", help="Filter providers (e.g. akshare_sina)")

    p_fetch = sub.add_parser("fetch-market-snapshot", help="Fetch routed market data")
    p_fetch.add_argument("--datasets", help="Comma-separated dataset names")
    p_fetch.add_argument("--persist", action="store_true", help="Save to data lake")
    p_fetch.add_argument("--live-only", action="store_true", help="Live route; exclude manual")
    p_fetch.add_argument("--latest-available", action="store_true", help="Latest-available route")
    p_fetch.add_argument("--provider", help="Restrict to one provider")

    p_val = sub.add_parser("validate-latest-snapshot", help="Validate normalized snapshot")
    p_val.add_argument("--dataset", default="spot_quotes")
    p_val.add_argument("--date", help="YYYY-MM-DD (legacy latest pointer)")
    p_val.add_argument("--run-id", help="Bind validation to fetch run")
    p_val.add_argument("--require-live", action="store_true")
    p_val.add_argument("--require-non-fixture", action="store_true")
    p_val.add_argument("--allow-end-of-day", action="store_true")
    p_val.add_argument("--provider", help="Expected provider name")
    p_val.add_argument("--market-date", help="Expected YYYY-MM-DD")
    p_val.add_argument("--max-age-minutes", type=int, help="Reject stale snapshots")

    p_imp = sub.add_parser("import-snapshot", help="Import CSV/JSON manual snapshot")
    p_imp.add_argument("path", help="Path to CSV or JSON file")
    p_imp.add_argument("--dataset", default="spot_quotes")
    p_imp.add_argument("--persist", action="store_true")

    p_daily = sub.add_parser("run-daily", help="Run daily intelligence pipeline")
    p_daily.add_argument("--fixture", help="Fixture name for offline run")
    p_daily.add_argument("--mode", choices=["latest-available", "fixture"], help="Operating mode")
    p_daily.add_argument("--run-id", help="Consume persisted snapshot by run_id")
    p_daily.add_argument("--no-cache", action="store_true")

    p_health = sub.add_parser("health-check", help="Health + acceptance check")
    p_health.add_argument("--live", action="store_true")
    p_health.add_argument("--strict", action="store_true", help="Fail if acceptance fails")

    sub.add_parser("scheduler-dry-run", help="Print scheduled jobs without running")
    sub.add_parser("build-validation-summary", help="Generate capability report")
    sub.add_parser("evaluate-paper-trades", help="Evaluate paper trade ledger")

    p_fabric = sub.add_parser("fabric-fetch", help="V2 fabric dataset fetch")
    p_fabric.add_argument("--datasets", help="Comma-separated datasets")
    p_fabric.add_argument("--persist", action="store_true")
    p_fabric.add_argument("--live-only", action="store_true")
    p_fabric.add_argument("--require-live", action="store_true")

    p_caps = sub.add_parser("capability-discovery", help="V2 provider capability discovery")
    p_caps.add_argument("--live", action="store_true")

    sub.add_parser("freshness-watchdog", help="Run live freshness watchdog")

    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
