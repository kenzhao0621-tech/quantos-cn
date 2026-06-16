#!/usr/bin/env python3
"""Master multi-provider V2 acceptance run and report generation."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LEDGER = ROOT / "docs" / "ai" / "daily-trading"
PY = ROOT / ".venv-china-quant" / "bin" / "python"


def _write(name: str, data: dict) -> None:
    LEDGER.mkdir(parents=True, exist_ok=True)
    (LEDGER / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# {name}", "", f"Generated: {data.get('generated_at', '')}", ""]
    for k, v in data.items():
        if k == "generated_at":
            continue
        lines.append(f"## {k}")
        lines.append("")
        if isinstance(v, (dict, list)):
            lines.append(f"```json\n{json.dumps(v, ensure_ascii=False, indent=2)}\n```")
        else:
            lines.append(str(v))
        lines.append("")
    (LEDGER / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def _run_test(script: str) -> bool:
    r = subprocess.run([str(PY), str(ROOT / "scripts" / script)], cwd=ROOT)
    return r.returncode == 0


def main() -> int:
    now = datetime.now().isoformat(timespec="seconds")
    pre_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    test_scripts = [
        ("multiprovider_v2", "run-multiprovider-v2-tests.py"),
        ("provider_recovery", "run-provider-recovery-tests.py"),
        ("paper_ledger", "run-paper-ledger-tests.py"),
        ("next_session", "run-next-session-tests.py"),
        ("v4_deterministic", "run-v4-deterministic-tests.py"),
    ]
    tests: dict[str, bool] = {}
    for name, script in test_scripts:
        tests[name] = _run_test(script)

    from quant._config import load_config, _DEFAULT_COVERAGE
    from quant.provider_base_v2 import discover_capabilities
    from quant.market_data_fabric import MarketDataFabric
    from quant.freshness_watchdog import run_freshness_watchdog
    from quant.indices_store import fetch_and_persist_indices, load_index_summary
    from quant.historical_store import persist_daily_partition, coverage_report
    from quant.candidate_data_gate import evaluate_candidate_readiness
    from quant.sector_store import persist_sector_boards, sector_coverage_report
    from quant.fundamental_store import persist_fundamentals, fundamental_coverage_report
    from quant.disclosure_store import persist_disclosures, disclosure_coverage_report
    from quant.point_in_time import evaluate_point_in_time_integrity
    from quant.backtest_integrity import evaluate_backtest_integrity
    from quant.feature_store import build_feature_summary
    from quant.run_context import new_run_id
    from quant.data_lake import save_snapshot
    from quant import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED

    coverage = load_config("data_coverage", defaults=_DEFAULT_COVERAGE)
    _write("01_DATA_COVERAGE_MATRIX", {"generated_at": now, **coverage})

    multimodal_ok = None
    if (ROOT / "scripts/run-multimodal-tests.py").exists():
        multimodal_ok = _run_test("run-multimodal-tests.py")
    _write("02_TEST_READINESS_REPORT", {
        "generated_at": now,
        "tests": tests,
        "all_passed": all(tests.values()),
        "multimodal_tests": multimodal_ok,
    })

    fabric = MarketDataFabric()
    caps = discover_capabilities(fabric.registry, probe_live=False)
    _write("03_PROVIDER_CAPABILITY_REPORT", {"generated_at": now, **caps.to_dict()})

    live_providers = []
    for row in caps.providers:
        ds = (row.get("capabilities") or {}).get("datasets", {})
        if any("REALTIME" in str(v).upper() or "LIVE" in str(v).upper() for v in ds.values()):
            live_providers.append(row)
    _write("03A_REALTIME_PROVIDER_DUE_DILIGENCE", {
        "generated_at": now,
        "live_capable_providers": live_providers,
        "licensed_realtime": ["rqdata", "qmt_market_data", "jqdata"],
        "verified_public_live": ["akshare_sina"],
        "notes": "Licensed paths require credentials; unconfigured providers are skipped not faked.",
    })

    run_id = new_run_id()
    from quant.freshness_contract import market_session_status
    _, session_open = market_session_status()
    require_live = session_open

    snap = fabric.fetch_market_snapshot(
        live_only=True,
        require_live=require_live,
        datasets=[
            "spot_quotes", "trading_calendar", "indices", "index_daily",
            "security_master", "sector_boards", "fundamentals", "official_disclosures",
        ],
    )
    spot = snap.get("spot_quotes")
    winner = spot.result if spot and spot.result else None
    if not winner and not session_open:
        snap_eod = fabric.fetch_market_snapshot(
            live_only=False,
            require_live=False,
            datasets=["spot_quotes"],
        )
        spot_eod = snap_eod.get("spot_quotes")
        if spot_eod and spot_eod.ok and spot_eod.result:
            spot = spot_eod
            winner = spot_eod.result
            save_snapshot(
                "spot_quotes", run_id=run_id,
                raw_payload=winner.payload,
                normalized_payload=winner.payload,
                provider=winner.provider,
                provenance={
                    "freshness": winner.freshness,
                    "is_live": False,
                    "endpoint": winner.endpoint,
                    "note": "post-close snapshot — not labeled live",
                },
            )

    for ds, fr in snap.items():
        if fr.ok and fr.result:
            save_snapshot(
                ds, run_id=run_id,
                raw_payload=fr.result.payload,
                normalized_payload=fr.result.payload,
                provider=fr.result.provider,
                provenance={
                    "freshness": fr.result.freshness,
                    "is_live": fr.result.is_live,
                    "endpoint": fr.result.endpoint,
                },
            )

    watchdog = run_freshness_watchdog(fabric=fabric, probe_live=True)
    _write("03B_LIVE_FRESHNESS_WATCHDOG_REPORT", {"generated_at": now, **watchdog})

    if spot and spot.cross_source:
        _write("03C_CROSS_SOURCE_RECONCILIATION_REPORT", {"generated_at": now, **spot.cross_source})
    else:
        _write("03C_CROSS_SOURCE_RECONCILIATION_REPORT", {
            "generated_at": now,
            "dataset": "spot_quotes",
            "compared": 0,
            "quarantine": False,
            "note": "single live source available",
        })

    idx_report = fetch_and_persist_indices(days=250)
    _write("04_INDEX_COMPLETION_REPORT", {"generated_at": now, **idx_report})

    hist_manifests = []
    cal = snap.get("trading_calendar")
    if cal and cal.ok and cal.result:
        days = cal.result.payload.get("days", [])
        norm = [d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in days]
        from quant.providers.tushare_provider import TushareProvider
        tp = TushareProvider()
        if tp.configured():
            for td in norm[-5:]:
                td8 = td.replace("-", "")
                r = tp.fetch("daily_bars", trade_date=td8)
                if r.ok and isinstance(r.payload, dict):
                    rows = r.payload.get("rows", [])
                    if rows:
                        hist_manifests.append(persist_daily_partition(td, rows, provider="tushare", run_id=run_id))
    _write("05_HISTORICAL_COVERAGE_REPORT", {
        "generated_at": now, "partitions": hist_manifests, **coverage_report(),
    })

    sector_fr = snap.get("sector_boards")
    if sector_fr and sector_fr.ok and sector_fr.result:
        rows = sector_fr.result.payload.get("rows", []) if isinstance(sector_fr.result.payload, dict) else []
        if rows:
            persist_sector_boards(rows, provider=sector_fr.result.provider, run_id=run_id)
    _write("06_SECTOR_COMPLETION_REPORT", {"generated_at": now, **sector_coverage_report()})

    fund_fr = snap.get("fundamentals")
    if fund_fr and fund_fr.ok and fund_fr.result:
        rows = fund_fr.result.payload.get("rows", []) if isinstance(fund_fr.result.payload, dict) else []
        if rows:
            persist_fundamentals(rows, provider=fund_fr.result.provider, run_id=run_id)
    _write("07_FUNDAMENTAL_COMPLETION_REPORT", {"generated_at": now, **fundamental_coverage_report()})

    disc_fr = snap.get("official_disclosures")
    if disc_fr and disc_fr.ok and disc_fr.result:
        rows = disc_fr.result.payload.get("rows", []) if isinstance(disc_fr.result.payload, dict) else []
        if rows:
            persist_disclosures(rows, provider=disc_fr.result.provider, run_id=run_id)
    _write("08_DISCLOSURE_COVERAGE_REPORT", {"generated_at": now, **disclosure_coverage_report()})

    pit = evaluate_point_in_time_integrity(
        as_of_date=datetime.now().strftime("%Y-%m-%d"),
        snapshot_market_date=winner.market_date if winner else None,
    )
    _write("09_POINT_IN_TIME_INTEGRITY_REPORT", {"generated_at": now, **pit.to_dict()})

    bt = evaluate_backtest_integrity()
    _write("10_BACKTEST_INTEGRITY_REPORT", {"generated_at": now, **bt.to_dict()})

    feature_summary = build_feature_summary()

    readiness = evaluate_candidate_readiness(
        run_id=run_id,
        spot_row_count=winner.row_count if winner else 0,
        spot_provider=winner.provider if winner else "",
        quality_passed=bool(spot and spot.ok),
    )
    _write("11_CANDIDATE_READINESS_REPORT", {"generated_at": now, **readiness.to_dict()})

    _write("12_NEXT_TRADING_DAY_RESEARCH_CANDIDATE", {
        "generated_at": now,
        "run_id": run_id,
        "decision": "BLOCKED_BY_DATA" if not readiness.ready else "ELIGIBLE_FOR_SCREENING",
        "maturity": readiness.maturity,
        "rejection_reasons": readiness.rejection_reasons,
    })

    ledger_path = LEDGER / "PAPER_SIGNAL_LEDGER.jsonl"
    ledger_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines() if ledger_path.exists() else []
    _write("13_PAPER_VALIDATION_STATUS", {
        "generated_at": now,
        "paper_trading_only": PAPER_TRADING_ONLY,
        "ledger_entries": len(ledger_lines),
        "status": "active" if ledger_lines else "empty",
    })

    maturity = readiness.maturity
    _write("14_FINAL_MASTER_CAPABILITY_REPORT", {
        "generated_at": now,
        "pre_change_commit": pre_commit,
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True,
        ).strip(),
        "run_id": run_id,
        "session_open": session_open,
        "require_live_used": require_live,
        "live_blocked_reason": "market closed" if not session_open else None,
        "spot_provider": winner.provider if winner else None,
        "row_count": winner.row_count if winner else 0,
        "data_date": winner.market_date if winner else None,
        "tests": tests,
        "maturity": maturity,
        "decision": "BLOCKED_BY_DATA" if not readiness.ready else "ELIGIBLE_FOR_SCREENING",
        "paper_trading_only": PAPER_TRADING_ONLY,
        "real_money_execution_disabled": REAL_MONEY_EXECUTION_DISABLED,
        "feature_store": feature_summary,
        "backup": ".cursor-backups/quant-master-readiness-20260616-193503",
    })

    print(json.dumps({
        "run_id": run_id,
        "maturity": maturity,
        "tests": tests,
        "spot_provider": winner.provider if winner else None,
        "row_count": winner.row_count if winner else 0,
        "decision": "BLOCKED_BY_DATA" if not readiness.ready else "ELIGIBLE_FOR_SCREENING",
    }, indent=2))
    return 0 if all(tests.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
