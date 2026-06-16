"""Candidate-grade data backfill orchestration with checkpointing."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_ROOT = ROOT / "data" / "manifests" / "backfill"

BAOSTOCK_INDEX_MAP = {
    "000001.SH": ("sh.000001", "SSE Composite"),
    "000300.SH": ("sh.000300", "CSI 300"),
    "000905.SH": ("sh.000905", "CSI 500"),
    "000852.SH": ("sh.000852", "CSI 1000"),
    "000688.SH": ("sh.000688", "STAR 50"),
    "399006.SZ": ("sz.399006", "ChiNext"),
    "399001.SZ": ("sz.399001", "Shenzhen Component"),
}


def _checkpoint(name: str) -> dict[str, Any]:
    p = CHECKPOINT_ROOT / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(name: str, data: dict[str, Any]) -> None:
    CHECKPOINT_ROOT.mkdir(parents=True, exist_ok=True)
    p = CHECKPOINT_ROOT / f"{name}.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _trade_dates_baostock(days: int = 300) -> list[str]:
    import baostock as bs

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    bs.login()
    rs = bs.query_trade_dates(start_date=start, end_date=end)
    out: list[str] = []
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if row[1] == "1":
            out.append(row[0].replace("-", ""))
    bs.logout()
    return out


def update_indices(*, min_bars: int = 250, provider: str = "baostock") -> dict[str, Any]:
    from quant.indices_store import INDEX_ROOT, MAJOR_INDICES

    INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    parquet_dir = ROOT / "data" / "parquet" / "indices"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"provider": provider, "indices": {}, "checked_at": datetime.now().isoformat(timespec="seconds")}

    if provider == "baostock":
        import baostock as bs

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=min_bars * 2)).strftime("%Y-%m-%d")
        bs.login()
        for ts_code, (bs_code, name) in BAOSTOCK_INDEX_MAP.items():
            path = INDEX_ROOT / f"{ts_code.replace('.', '_')}.json"
            if path.exists():
                cached = json.loads(path.read_text(encoding="utf-8"))
                if len(cached.get("bars", [])) >= 120:
                    report["indices"][ts_code] = {"bars": len(cached["bars"]), "cached": True, "name": name}
                    continue
            rs = bs.query_history_k_data_plus(
                bs_code, "date,open,high,low,close,volume,amount",
                start_date=start, end_date=end, frequency="d", adjustflag="3",
            )
            bars = []
            while rs.error_code == "0" and rs.next():
                r = rs.get_row_data()
                bars.append({
                    "trade_date": r[0].replace("-", ""),
                    "open": float(r[1] or 0), "high": float(r[2] or 0),
                    "low": float(r[3] or 0), "close": float(r[4] or 0),
                    "vol": float(r[5] or 0), "amount": float(r[6] or 0),
                    "ts_code": ts_code,
                })
            if bars:
                path.write_text(json.dumps({"ts_code": ts_code, "name": name, "bars": bars, "provider": provider}, ensure_ascii=False), encoding="utf-8")
                try:
                    import pandas as pd
                    pq = parquet_dir / f"{ts_code.replace('.', '_')}.parquet"
                    pd.DataFrame(bars).to_parquet(pq, index=False)
                except Exception:
                    pass
            report["indices"][ts_code] = {"bars": len(bars), "name": name, "error": None if bars else "empty"}
        bs.logout()
    else:
        from quant.indices_store import fetch_and_persist_indices
        report = fetch_and_persist_indices(days=min_bars, provider_name=provider)

    available = sum(1 for v in report.get("indices", {}).values() if v.get("bars", 0) >= 120)
    report["available_count"] = available
    report["candidate_gate"] = available >= 3
    _save_checkpoint("indices", report)
    return report


def update_daily_bars(*, target_days: int = 120, max_new: int = 80) -> dict[str, Any]:
    from quant.historical_store import MANIFEST_ROOT, persist_daily_partition, coverage_report
    from quant.providers.tushare_provider import TushareProvider

    cp = _checkpoint("daily_bars")
    done = set(cp.get("completed_dates", []))
    tp = TushareProvider()
    if not tp.configured():
        return {"error": "TUSHARE_TOKEN not configured", "status": "PERMISSION_UNAVAILABLE"}

    dates = _trade_dates_baostock(days=target_days + 30)
    dates = sorted(dates)[-target_days:]
    pending = [d for d in dates if d not in done][-max_new:]

    manifests = []
    errors: list[str] = []
    for i, td in enumerate(pending):
        r = tp.fetch("daily_bars", trade_date=td)
        if not r.ok:
            errors.append(f"{td}: {r.error}")
            if "频率" in (r.error or "") or "limit" in (r.error or "").lower():
                time.sleep(65)
                r = tp.fetch("daily_bars", trade_date=td)
        if r.ok and isinstance(r.payload, dict):
            rows = r.payload.get("rows", [])
            if rows:
                manifests.append(persist_daily_partition(td, rows, provider="tushare", run_id=cp.get("run_id", "")))
                done.add(td)
        if i and i % 5 == 0:
            time.sleep(1.5)

    cp["completed_dates"] = sorted(done)
    cp["last_run"] = datetime.now().isoformat(timespec="seconds")
    _save_checkpoint("daily_bars", cp)
    cov = coverage_report()
    return {
        "new_partitions": len(manifests),
        "pending_attempted": len(pending),
        "errors": errors[:10],
        **cov,
        "candidate_gate": cov.get("partition_count", 0) >= 60 or len(done) >= 60,
    }


def update_sectors() -> dict[str, Any]:
    from quant.sector_store import persist_sector_boards, sector_coverage_report
    from quant.providers.tushare_provider import TushareProvider

    tp = TushareProvider()
    if not tp.configured():
        return {"status": "PERMISSION_UNAVAILABLE", **sector_coverage_report()}
    r = tp.fetch("security_master")
    if not r.ok or not isinstance(r.payload, dict):
        return {"error": r.error, **sector_coverage_report()}
    rows = []
    for row in r.payload.get("rows", []):
        ind = row.get("industry") or "UNKNOWN"
        rows.append({
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "sector_code": ind,
            "sector_name": ind,
            "effective_date": row.get("list_date", ""),
            "expiry_date": "",
            "provider": "tushare_stock_basic",
        })
    if rows:
        persist_sector_boards(rows, provider="tushare")
    rep = sector_coverage_report()
    rep["row_count"] = len(rows)
    rep["unique_sectors"] = len({r["sector_name"] for r in rows})
    rep["candidate_gate"] = rep.get("total_rows", 0) >= 3000 and rep.get("unique_sectors", 0) >= 20
    _save_checkpoint("sectors", rep)
    return rep


def update_fundamentals() -> dict[str, Any]:
    from quant.fundamental_store import persist_fundamentals, fundamental_coverage_report
    from quant.providers.tushare_provider import TushareProvider

    tp = TushareProvider()
    if not tp.configured():
        return {"status": "PERMISSION_UNAVAILABLE", **fundamental_coverage_report()}
    start = time.perf_counter()
    try:
        pro = tp._pro()
        trade_date = tp._latest_completed_trade_date(pro)
        df = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,trade_date,turnover_rate,pe,pb,ps,dv_ttm,total_mv,circ_mv",
        )
        rows = df.to_dict(orient="records") if df is not None else []
        for row in rows:
            row["announcement_date"] = trade_date
            row["report_period"] = trade_date
            row["provider"] = "tushare_daily_basic"
        if rows:
            persist_fundamentals(rows, provider="tushare")
        rep = fundamental_coverage_report()
        rep["trade_date"] = trade_date
        rep["row_count"] = len(rows)
        rep["candidate_gate"] = len(rows) >= 1000
        rep["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 2)
        _save_checkpoint("fundamentals", rep)
        return rep
    except Exception as e:
        return {"error": str(e), **fundamental_coverage_report()}


def update_disclosures() -> dict[str, Any]:
    from quant.disclosure_store import persist_disclosures, disclosure_coverage_report
    from quant.providers.tushare_provider import TushareProvider

    tp = TushareProvider()
    if not tp.configured():
        return {"status": "PERMISSION_UNAVAILABLE", **disclosure_coverage_report()}
    try:
        pro = tp._pro()
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        rows: list[dict[str, Any]] = []
        try:
            df = pro.anns(start_date=start, end_date=end)
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    rows.append({
                        "ts_code": r.get("ts_code", ""),
                        "ann_date": str(r.get("ann_date", "")),
                        "title": str(r.get("title", "")),
                        "category": "announcement",
                        "provider": "tushare_anns",
                        "source": "tushare",
                    })
        except Exception:
            pass
        if rows:
            persist_disclosures(rows, provider="tushare")
        rep = disclosure_coverage_report()
        rep["row_count"] = len(rows)
        rep["candidate_gate"] = len(rows) >= 50
        _save_checkpoint("disclosures", rep)
        return rep
    except Exception as e:
        return {"error": str(e), **disclosure_coverage_report()}
