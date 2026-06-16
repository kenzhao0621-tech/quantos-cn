#!/usr/bin/env python3
"""Focused live AKShare provider recovery test — no fixture/manual data."""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_MD = ROOT / "docs" / "ai" / "daily-trading" / "LIVE_PROVIDER_RECOVERY_REPORT.md"
OUT_JSON = ROOT / "docs" / "ai" / "daily-trading" / "LIVE_PROVIDER_RECOVERY_REPORT.json"
VENV_PY = ROOT / ".venv-china-quant" / "bin" / "python"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _probe(
    provider_id: str,
    function_name: str,
    fn: Callable[[], Any],
    *,
    row_counter: Optional[Callable[[Any], int]] = None,
    column_extractor: Optional[Callable[[Any], list[str]]] = None,
    market_date_extractor: Optional[Callable[[Any], Optional[str]]] = None,
) -> dict[str, Any]:
    import time

    rec: dict[str, Any] = {
        "provider_id": provider_id,
        "function_called": function_name,
        "start_time": _now(),
        "end_time": None,
        "latency_ms": None,
        "row_count": 0,
        "columns": [],
        "market_date": None,
        "exception_class": None,
        "exception_message": None,
        "success": False,
    }
    t0 = time.perf_counter()
    try:
        result = fn()
        rec["end_time"] = _now()
        rec["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        if row_counter:
            rec["row_count"] = row_counter(result)
        if column_extractor:
            rec["columns"] = column_extractor(result)
        if market_date_extractor:
            rec["market_date"] = market_date_extractor(result)
        rec["success"] = rec["row_count"] > 0 or (
            provider_id == "index_provider" and isinstance(result, dict)
        )
    except Exception as e:
        rec["end_time"] = _now()
        rec["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        rec["exception_class"] = type(e).__name__
        rec["exception_message"] = str(e)
    return rec


def _df_rows(df) -> int:
    return len(df) if df is not None else 0


def _df_cols(df) -> list[str]:
    return list(df.columns) if df is not None and hasattr(df, "columns") else []


def _spot_market_date(df) -> Optional[str]:
    for col in ("日期", "date", "时间", "time"):
        if col in df.columns and len(df):
            return str(df[col].iloc[0])
    return datetime.now().strftime("%Y-%m-%d")


def run_akshare_probes() -> list[dict[str, Any]]:
    import akshare as ak

    probes: list[tuple[str, str, Callable]] = [
        ("eastmoney_full_market", "ak.stock_zh_a_spot_em", lambda: ak.stock_zh_a_spot_em()),
        ("eastmoney_shanghai", "ak.stock_sh_a_spot_em", lambda: ak.stock_sh_a_spot_em()),
        ("eastmoney_shenzhen", "ak.stock_sz_a_spot_em", lambda: ak.stock_sz_a_spot_em()),
        ("eastmoney_beijing", "ak.stock_bj_a_spot_em", lambda: ak.stock_bj_a_spot_em()),
        ("sina_spot", "ak.stock_zh_a_spot", lambda: ak.stock_zh_a_spot()),
        ("tencent_spot", "ak.stock_zh_a_spot_tx", lambda: ak.stock_zh_a_spot_tx()),
        ("index_provider", "ak.stock_zh_index_spot_em", lambda: ak.stock_zh_index_spot_em()),
        (
            "trading_calendar",
            "ak.tool_trade_date_hist_sina",
            lambda: ak.tool_trade_date_hist_sina(),
        ),
    ]
    results = []
    for pid, fname, fn in probes:
        if pid == "trading_calendar":

            def _cal_counter(r):
                return len(r) if hasattr(r, "__len__") else 0

            def _cal_cols(r):
                return list(r.columns) if hasattr(r, "columns") else ["trade_date"]

            def _cal_date(r):
                if hasattr(r, "iloc") and len(r):
                    col = "trade_date" if "trade_date" in r.columns else r.columns[0]
                    return str(r[col].iloc[-1])
                return None

            results.append(
                _probe(pid, fname, fn, row_counter=_cal_counter, column_extractor=_cal_cols, market_date_extractor=_cal_date)
            )
        elif pid == "index_provider":
            results.append(
                _probe(
                    pid,
                    fname,
                    fn,
                    row_counter=_df_rows,
                    column_extractor=_df_cols,
                    market_date_extractor=lambda _: datetime.now().strftime("%Y-%m-%d"),
                )
            )
        else:
            results.append(
                _probe(
                    pid,
                    fname,
                    fn,
                    row_counter=_df_rows,
                    column_extractor=_df_cols,
                    market_date_extractor=_spot_market_date,
                )
            )
    return results


def try_merge_split(probes: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Merge SH/SZ/BJ if full market failed and segments succeeded with compatible schemas."""
    full = next((p for p in probes if p["provider_id"] == "eastmoney_full_market"), None)
    if full and full.get("success"):
        return None
    segments = [p for p in probes if p["provider_id"] in (
        "eastmoney_shanghai", "eastmoney_shenzhen", "eastmoney_beijing"
    ) and p.get("success")]
    if not segments:
        return {"merged": False, "reason": "no successful segments"}
    dates = {p.get("market_date") for p in segments}
    col_sets = [set(p.get("columns", [])) for p in segments]
    if len(dates - {None}) > 1:
        return {"merged": False, "reason": f"incompatible market dates: {dates}"}
    base_cols = col_sets[0] if col_sets else set()
    if not all(s == base_cols or s.issubset(base_cols) or base_cols.issubset(s) for s in col_sets[1:]):
        return {"merged": False, "reason": "schema mismatch across segments", "columns": [list(c) for c in col_sets]}
    total_rows = sum(p.get("row_count", 0) for p in segments)
    return {
        "merged": True,
        "segments": [p["provider_id"] for p in segments],
        "total_row_count": total_rows,
        "market_date": next(iter(dates - {None}), None),
        "columns": list(base_cols),
    }


def run_quant_commands() -> dict[str, Any]:
    py = str(VENV_PY if VENV_PY.exists() else sys.executable)
    cmds = [
        ([py, "-m", "quant", "provider-check", "--live", "--provider", "akshare"], "provider_check"),
        ([py, "-m", "quant", "fetch-market-snapshot", "--persist", "--live-only"], "fetch_snapshot"),
        ([py, "-m", "quant", "validate-latest-snapshot", "--dataset", "spot_quotes"], "validate_snapshot"),
    ]
    out: dict[str, Any] = {}
    for argv, key in cmds:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        out[key] = {
            "exit_code": r.returncode,
            "stdout": r.stdout[-8000:] if len(r.stdout) > 8000 else r.stdout,
            "stderr": r.stderr[-2000:] if len(r.stderr) > 2000 else r.stderr,
        }
    return out


def main() -> int:
    report: dict[str, Any] = {
        "generated_at": _now(),
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "venv": str(ROOT / ".venv-china-quant"),
        "akshare_version_before": None,
        "akshare_version_after": None,
        "akshare_upgraded": False,
        "probes": [],
        "merge_attempt": None,
        "data_quality_gate": None,
        "recovery_success": False,
        "quant_commands": {},
    }

    # Version check
    try:
        report["akshare_version_before"] = importlib.metadata.version("akshare")
    except importlib.metadata.PackageNotFoundError:
        report["akshare_version_before"] = "NOT_INSTALLED"

    # Upgrade if not latest (already checked externally; pip install -U akshare)
    if VENV_PY.exists():
        r = subprocess.run(
            [str(VENV_PY), "-m", "pip", "install", "-U", "akshare"],
            capture_output=True,
            text=True,
        )
        report["pip_upgrade_exit"] = r.returncode
        report["pip_upgrade_tail"] = (r.stdout + r.stderr)[-500:]
    try:
        report["akshare_version_after"] = importlib.metadata.version("akshare")
    except importlib.metadata.PackageNotFoundError:
        report["akshare_version_after"] = "NOT_INSTALLED"
    report["akshare_upgraded"] = report["akshare_version_before"] != report["akshare_version_after"]

    # Disable cache for live recovery
    import os
    os.environ["CHINA_QUANT_NO_CACHE"] = "1"

    # Hide manual imports so composite won't use them
    imports_dir = ROOT / "data" / "imports"
    backup_imports = ROOT / "data" / ".imports_recovery_backup"
    imports_moved = False
    if imports_dir.exists() and any(imports_dir.iterdir()):
        if backup_imports.exists():
            import shutil
            shutil.rmtree(backup_imports)
        imports_dir.rename(backup_imports)
        imports_moved = True
    report["manual_imports_quarantined"] = imports_moved

    try:
        report["probes"] = run_akshare_probes()
        report["merge_attempt"] = try_merge_split(report["probes"])

        # DQ gate on best live spot payload
        from quant.data_quality import run_snapshot_quality_checks
        from quant.composite_provider import CompositeMarketDataProvider

        composite = CompositeMarketDataProvider()
        # Exclude manual from registry for this test
        if "manual_snapshot" in composite.registry:
            del composite.registry["manual_snapshot"]
        cr = composite.fetch("spot_quotes")
        if cr.ok and cr.result:
            qr = run_snapshot_quality_checks(
                "spot_quotes", cr.result.payload, data_hash=cr.result.data_hash or "", min_rows=100
            )
            report["data_quality_gate"] = {
                "provider": cr.result.provider,
                "passed": qr.passed,
                "result": qr.to_dict(),
                "attempts": [a.to_dict() for a in cr.attempts],
            }
            report["recovery_success"] = (
                qr.passed
                and cr.result.provider.startswith("akshare")
                and cr.result.freshness not in ("FIXTURE", "MANUAL_IMPORT")
            )
        else:
            report["data_quality_gate"] = {
                "provider": None,
                "passed": False,
                "error": "composite spot_quotes fetch failed",
                "attempts": [a.to_dict() for a in cr.attempts],
            }

        report["quant_commands"] = run_quant_commands()
    finally:
        if imports_moved and backup_imports.exists():
            backup_imports.rename(imports_dir)

    # Render markdown
    lines = [
        "# Live Provider Recovery Report",
        "",
        f"- **Generated**: {report['generated_at']}",
        f"- **Branch**: `{report['branch']}` @ `{report['commit']}`",
        f"- **AKShare**: {report['akshare_version_before']} → {report['akshare_version_after']} (upgraded: {report['akshare_upgraded']})",
        f"- **Recovery success**: **{report['recovery_success']}**",
        "",
        "## Provider probes",
        "",
        "| Provider | Function | Latency ms | Rows | Success | Exception |",
        "|----------|----------|------------|------|---------|-----------|",
    ]
    for p in report["probes"]:
        exc = f"{p.get('exception_class')}: {p.get('exception_message', '')[:60]}" if p.get("exception_class") else "—"
        lines.append(
            f"| {p['provider_id']} | `{p['function_called']}` | {p.get('latency_ms')} | {p.get('row_count')} | {p.get('success')} | {exc} |"
        )

    if report.get("merge_attempt"):
        lines.extend(["", "## Split-market merge", "", f"```json\n{json.dumps(report['merge_attempt'], indent=2)}\n```"])

    if report.get("data_quality_gate"):
        dq = report["data_quality_gate"]
        lines.extend([
            "",
            "## Data Quality Gate",
            "",
            f"- Provider: `{dq.get('provider')}`",
            f"- Passed: **{dq.get('passed')}**",
        ])

    lines.extend(["", "## Quant CLI", ""])
    for k, v in report.get("quant_commands", {}).items():
        lines.append(f"- `{k}`: exit {v.get('exit_code')}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"recovery_success": report["recovery_success"], "paths": {"md": str(OUT_MD), "json": str(OUT_JSON)}}, indent=2))
    return 0 if report["recovery_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
