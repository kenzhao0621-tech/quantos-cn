"""Major index persistence and validation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = ROOT / "data" / "indices"

MAJOR_INDICES = {
    "000001.SH": "SSE Composite",
    "000300.SH": "CSI 300",
    "000905.SH": "CSI 500",
    "000852.SH": "CSI 1000",
    "000688.SH": "STAR 50",
    "399006.SZ": "ChiNext",
    "399001.SZ": "Shenzhen Component",
}


def fetch_and_persist_indices(
    *,
    days: int = 250,
    provider_name: str = "tushare",
) -> dict[str, Any]:
    from quant.market_data_fabric import MarketDataFabric

    fabric = MarketDataFabric()
    provider = fabric.registry.get(provider_name)
    if not provider or not provider.configured():
        return {"error": f"{provider_name} not configured", "persisted": 0}

    INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"indices": {}, "provider": provider_name, "checked_at": datetime.now().isoformat(timespec="seconds")}

    try:
        pro = provider._pro() if hasattr(provider, "_pro") else None
    except Exception:
        pro = None

    end = datetime.now()
    start = end - timedelta(days=days * 2)
    start_s = start.strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")

    for ts_code, name in MAJOR_INDICES.items():
        bars: list[dict[str, Any]] = []
        path = INDEX_ROOT / f"{ts_code.replace('.', '_')}.json"
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            bars = cached.get("bars", [])
            if len(bars) >= 120:
                report["indices"][ts_code] = {
                    "name": name, "bars": len(bars), "cached": True,
                    "first": bars[0].get("trade_date", ""),
                    "last": bars[-1].get("trade_date", ""),
                    "path": str(path.relative_to(ROOT)),
                }
                continue
        try:
            if pro is not None:
                import time
                import tushare as ts  # noqa: F401
                time.sleep(1.2)
                df = pro.index_daily(ts_code=ts_code, start_date=start_s, end_date=end_s)
                if df is not None and not df.empty:
                    bars = df.to_dict(orient="records")
        except Exception as e:
            report["indices"][ts_code] = {"name": name, "error": str(e), "bars": 0}
            continue

        if bars:
            path = INDEX_ROOT / f"{ts_code.replace('.', '_')}.json"
            path.write_text(json.dumps({"ts_code": ts_code, "name": name, "bars": bars}, ensure_ascii=False), encoding="utf-8")
            report["indices"][ts_code] = {
                "name": name, "bars": len(bars),
                "first": bars[0].get("trade_date", ""),
                "last": bars[-1].get("trade_date", ""),
                "path": str(path.relative_to(ROOT)),
            }
        else:
            report["indices"][ts_code] = {"name": name, "bars": 0, "error": "no data"}

    available = sum(1 for v in report["indices"].values() if v.get("bars", 0) >= 120)
    report["available_count"] = available
    report["candidate_gate"] = available >= 3
    return report


def load_index_summary() -> dict[str, Any]:
    if not INDEX_ROOT.exists():
        return {"available": 0, "indices": {}}
    out = {}
    for path in INDEX_ROOT.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        bars = data.get("bars", [])
        out[data.get("ts_code", path.stem)] = {"bars": len(bars), "name": data.get("name", "")}
    return {"available": len(out), "indices": out, "meets_minimum": len(out) >= 3}
